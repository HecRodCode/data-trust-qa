import csv
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from data_trust_qa.config.environment import load_project_environment
from data_trust_qa.database.bootstrap import _build_load_script, load_into_postgres
from data_trust_qa.database.process_b import _build_process_script
from data_trust_qa.domain.models import GenerationConfig
from data_trust_qa.generation.dataset import generate_dataset
from data_trust_qa.generation.exporters import write_dataset


class GenerateDatasetTests(unittest.TestCase):
    def test_default_configuration_matches_agreed_population(self) -> None:
        config = GenerationConfig()

        self.assertEqual(
            (
                config.customer_count,
                config.account_count,
                config.payment_count,
                config.balance_count,
            ),
            (4_000, 6_000, 12_000, 3_000),
        )

    def test_generation_is_reproducible_for_same_seed(self) -> None:
        config = GenerationConfig(seed=7)

        self.assertEqual(generate_dataset(config), generate_dataset(config))

    def test_generated_relationships_and_business_keys_are_valid(self) -> None:
        dataset = generate_dataset(GenerationConfig(seed=11))
        customer_ids = {customer.customer_id for customer in dataset.customers}
        account_ids = {account.credit_account_id for account in dataset.credit_accounts}

        self.assertTrue(
            all(
                account.customer_id in customer_ids
                for account in dataset.credit_accounts
            )
        )
        self.assertTrue(
            all(payment.credit_account_id in account_ids for payment in dataset.payments)
        )
        self.assertTrue(
            all(balance.credit_account_id in account_ids for balance in dataset.account_balances)
        )
        self.assertEqual(
            len({account.account_business_key for account in dataset.credit_accounts}),
            len(dataset.credit_accounts),
        )
        self.assertEqual(
            len({payment.payment_business_key for payment in dataset.payments}),
            len(dataset.payments),
        )
        self.assertEqual(
            len(
                {
                    (balance.credit_account_id, balance.cutoff_date)
                    for balance in dataset.account_balances
                }
            ),
            len(dataset.account_balances),
        )
        for balance in dataset.account_balances:
            components = (
                Decimal(balance.principal_balance)
                + Decimal(balance.interest_balance)
                + Decimal(balance.fees_balance)
            )
            self.assertEqual(Decimal(balance.total_balance), components)

    def test_export_contains_a_tables_and_raw_b_batch(self) -> None:
        config = GenerationConfig(
            seed=13,
            customer_count=2,
            account_count=3,
            payment_count=4,
            balance_count=3,
        )
        dataset = generate_dataset(config)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            write_dataset(dataset, output_dir, "TEST-BATCH")
            repeated_output_dir = output_dir / "repeat"
            write_dataset(
                generate_dataset(config),
                repeated_output_dir,
                "TEST-BATCH",
            )

            with (output_dir / "source_a" / "credit_accounts.csv").open(
                newline="", encoding="utf-8"
            ) as file:
                account_rows = list(csv.DictReader(file))
            with (output_dir / "landing_b.csv").open(
                newline="", encoding="utf-8"
            ) as file:
                landing_rows = list(csv.DictReader(file))

            self.assertEqual(len(account_rows), 3)
            self.assertEqual(len(landing_rows), 12)
            self.assertEqual(
                {row["batch_reference"] for row in landing_rows},
                {"TEST-BATCH"},
            )
            self.assertEqual(
                {row["entity_type"] for row in landing_rows},
                {"customers", "credit_accounts", "payments", "account_balances"},
            )
            self.assertTrue(
                all(
                    isinstance(json.loads(row["raw_payload"]), dict)
                    for row in landing_rows
                )
            )
            self.assertEqual(
                (output_dir / "landing_b.csv").read_bytes(),
                (repeated_output_dir / "landing_b.csv").read_bytes(),
            )

    def test_accounts_cannot_be_generated_without_customers(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one customer"):
            GenerationConfig(customer_count=0, account_count=1)

    def test_bootstrap_load_script_includes_transactional_csv_loads(self) -> None:
        config = GenerationConfig(
            seed=1,
            customer_count=2,
            account_count=3,
            payment_count=4,
            balance_count=5,
        )

        script = _build_load_script(
            Path("/project/database/schemas"),
            Path("/project/data/generated"),
            config,
        )

        self.assertIn("source_a.customers (2 rows)", script)
        self.assertIn("landing_b.received_records (14 rows)", script)
        self.assertIn("\\copy source_a.customers FROM", script)
        self.assertIn(
            "\\copy landing_b.received_records "
            "(batch_reference, entity_type, source_record_key, raw_payload) FROM",
            script,
        )
        self.assertIn("source_b.sql", script)
        self.assertIn("setval(pg_get_serial_sequence", script)

    def test_process_script_loads_entities_in_dependency_order(self) -> None:
        script = _build_process_script("BATCH-0001")

        self.assertLess(
            script.index("INSERT INTO source_b.customers"),
            script.index("INSERT INTO source_b.credit_accounts"),
        )
        self.assertLess(
            script.index("INSERT INTO source_b.credit_accounts"),
            script.index("INSERT INTO source_b.payments"),
        )
        self.assertLess(
            script.index("INSERT INTO source_b.payments"),
            script.index("INSERT INTO source_b.account_balances"),
        )
        self.assertIn("processing_status = 'aceptado'", script)
        self.assertIn("validation_errors = '[]'::JSONB", script)
        self.assertIn("LOCK TABLE", script)

    def test_process_script_escapes_batch_reference(self) -> None:
        script = _build_process_script("BATCH'0001")

        self.assertIn("'BATCH''0001'", script)
        self.assertNotIn("'BATCH'0001'", script)

    def test_bootstrap_reuses_existing_empty_schemas(self) -> None:
        schema_state = {
            "source_a": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
            "source_b": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
            "landing_b": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
        }
        table_counts = {
            "source_a.customers": 0,
            "source_a.credit_accounts": 0,
            "source_a.payments": 0,
            "source_a.account_balances": 0,
            "landing_b.received_records": 0,
        }
        completed_schema_inspection = subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout=json.dumps(schema_state), stderr=""
        )
        completed_table_counts = subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout=json.dumps(table_counts), stderr=""
        )
        completed_load = subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout="loaded\n", stderr=""
        )
        loaded_script: list[str] = []

        def run_psql_side_effect(
            executable: str,
            arguments: list[str],
            environment: dict[str, str],
        ) -> subprocess.CompletedProcess[str]:
            self.assertEqual(executable, "psql")
            self.assertEqual(environment, {})
            if "-c" in arguments:
                query = arguments[arguments.index("-c") + 1]
                if "jsonb_object_agg" in query:
                    return completed_schema_inspection
                return completed_table_counts
            if "--file" in arguments:
                loaded_script.append(
                    Path(arguments[arguments.index("--file") + 1]).read_text(
                        encoding="utf-8"
                    )
                )
                return completed_load
            self.fail(f"Unexpected psql arguments: {arguments}")

        with (
            patch("data_trust_qa.database.bootstrap._psql_path", return_value="psql"),
            patch("data_trust_qa.database.bootstrap._connection_environment", return_value={}),
            patch(
                "data_trust_qa.database.bootstrap._run_psql",
                side_effect=run_psql_side_effect,
            ),
            redirect_stdout(io.StringIO()) as output,
        ):
            reused_schemas = load_into_postgres(
                Path("/project/database/schemas"),
                Path("/project/data/generated"),
                GenerationConfig(),
            )

        self.assertEqual(reused_schemas, ("source_a", "source_b", "landing_b"))
        self.assertIn("Reusing existing schemas", output.getvalue())
        self.assertEqual(len(loaded_script), 1)
        self.assertIn("Reusing existing schemas and tables", loaded_script[0])
        self.assertNotIn("\\i ", loaded_script[0])

    def test_bootstrap_refuses_populated_target_tables(self) -> None:
        schema_state = {
            "source_a": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
            "source_b": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
            "landing_b": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
        }
        populated_counts = {
            "source_a.customers": 10,
            "source_a.credit_accounts": 0,
            "source_a.payments": 0,
            "source_a.account_balances": 0,
            "landing_b.received_records": 0,
        }
        schema_inspection = subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout=json.dumps(schema_state), stderr=""
        )
        count_inspection = subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout=json.dumps(populated_counts), stderr=""
        )
        with (
            patch("data_trust_qa.database.bootstrap._psql_path", return_value="psql"),
            patch("data_trust_qa.database.bootstrap._connection_environment", return_value={}),
            patch(
                "data_trust_qa.database.bootstrap._run_psql",
                side_effect=(schema_inspection, count_inspection),
            ) as run_psql,
        ):
            with self.assertRaisesRegex(
                RuntimeError, r"source_a\.customers=10"
            ):
                load_into_postgres(
                    Path("/project/database/schemas"),
                    Path("/project/data/generated"),
                    GenerationConfig(),
                )

        self.assertEqual(run_psql.call_count, 2)

    def test_bootstrap_refuses_partially_created_schema(self) -> None:
        schema_state = {
            "source_a": {
                "exists": True,
                "objects_present": True,
                "missing_tables": ["payments"],
                "missing_columns": {"payments": ["payment_id"]},
            },
            "source_b": {
                "exists": False,
                "objects_present": False,
                "missing_tables": [
                    "customers",
                    "credit_accounts",
                    "payments",
                    "account_balances",
                ],
                "missing_columns": {
                    "customers": ["customer_id"],
                    "credit_accounts": ["credit_account_id"],
                    "payments": ["payment_id"],
                    "account_balances": ["credit_account_id"],
                },
            },
            "landing_b": {
                "exists": False,
                "objects_present": False,
                "missing_tables": ["received_records"],
                "missing_columns": {"received_records": ["received_record_id"]},
            },
        }
        schema_inspection = subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout=json.dumps(schema_state), stderr=""
        )
        with (
            patch("data_trust_qa.database.bootstrap._psql_path", return_value="psql"),
            patch("data_trust_qa.database.bootstrap._connection_environment", return_value={}),
            patch(
                "data_trust_qa.database.bootstrap._run_psql",
                return_value=schema_inspection,
            ) as run_psql,
        ):
            with self.assertRaisesRegex(RuntimeError, "Schema source_a exists"):
                load_into_postgres(
                    Path("/project/database/schemas"),
                    Path("/project/data/generated"),
                    GenerationConfig(),
                )
        run_psql.assert_called_once()

    def test_bootstrap_refuses_existing_tables_missing_business_key_columns(
        self,
    ) -> None:
        schema_state = {
            "source_a": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {
                    "credit_accounts": ["account_business_key"],
                    "payments": ["payment_business_key"],
                },
            },
            "source_b": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
            "landing_b": {
                "exists": True,
                "objects_present": True,
                "missing_tables": [],
                "missing_columns": {},
            },
        }
        schema_inspection = subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout=json.dumps(schema_state), stderr=""
        )
        with (
            patch("data_trust_qa.database.bootstrap._psql_path", return_value="psql"),
            patch("data_trust_qa.database.bootstrap._connection_environment", return_value={}),
            patch(
                "data_trust_qa.database.bootstrap._run_psql",
                return_value=schema_inspection,
            ) as run_psql,
        ):
            with self.assertRaisesRegex(RuntimeError, "account_business_key"):
                load_into_postgres(
                    Path("/project/database/schemas"),
                    Path("/project/data/generated"),
                    GenerationConfig(),
                )
        run_psql.assert_called_once()

    def test_project_environment_loads_local_values_without_overriding_existing_env(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / ".env").write_text(
                "PGHOST=env-host\nPGPORT=5432\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"PGHOST": "existing-host"}, clear=True):
                load_project_environment(project_root)

                self.assertEqual(os.environ["PGHOST"], "existing-host")
                self.assertEqual(os.environ["PGPORT"], "5432")


if __name__ == "__main__":
    unittest.main()
