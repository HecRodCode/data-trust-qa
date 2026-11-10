import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from ..config.environment import load_project_environment
from ..domain.models import GenerationConfig
from ..generation.dataset import generate_dataset
from ..generation.exporters import write_dataset

SCHEMA_FILES = ("source_a.sql", "source_b.sql", "landing_b.sql")
SCHEMA_TABLES = {
    "source_a": (
        "customers",
        "credit_accounts",
        "payments",
        "account_balances",
    ),
    "source_b": (
        "customers",
        "credit_accounts",
        "payments",
        "account_balances",
    ),
    "landing_b": ("received_records",),
}
SCHEMA_COLUMNS = {
    "source_a": {
        "customers": ("customer_id", "document_type", "document_number"),
        "credit_accounts": (
            "credit_account_id",
            "account_business_key",
            "customer_id",
            "product_type",
            "opening_date",
            "account_status",
        ),
        "payments": (
            "payment_id",
            "payment_business_key",
            "credit_account_id",
            "payment_date",
            "payment_amount",
            "payment_status",
        ),
        "account_balances": (
            "credit_account_id",
            "cutoff_date",
            "principal_balance",
            "interest_balance",
            "fees_balance",
            "total_balance",
            "currency",
        ),
    },
    "source_b": {
        "customers": ("customer_id", "document_type", "document_number"),
        "credit_accounts": (
            "credit_account_id",
            "account_business_key",
            "customer_id",
            "product_type",
            "opening_date",
            "account_status",
        ),
        "payments": (
            "payment_id",
            "payment_business_key",
            "credit_account_id",
            "payment_date",
            "payment_amount",
            "payment_status",
        ),
        "account_balances": (
            "credit_account_id",
            "cutoff_date",
            "principal_balance",
            "interest_balance",
            "fees_balance",
            "total_balance",
            "currency",
        ),
    },
    "landing_b": {
        "received_records": (
            "received_record_id",
            "batch_reference",
            "entity_type",
            "source_record_key",
            "raw_payload",
            "received_at",
            "processing_status",
            "validation_errors",
        )
    },
}
SCHEMA_FILE_BY_NAME = dict(zip(SCHEMA_TABLES, SCHEMA_FILES, strict=True))


class SchemaState(TypedDict):
    exists: bool
    objects_present: bool
    missing_tables: list[str]
    missing_columns: dict[str, list[str]]


CSV_LOADS = (
    (
        "source_a.customers",
        "source_a/customers.csv",
        "customer_count",
        None,
    ),
    (
        "source_a.credit_accounts",
        "source_a/credit_accounts.csv",
        "account_count",
        None,
    ),
    (
        "source_a.payments",
        "source_a/payments.csv",
        "payment_count",
        None,
    ),
    (
        "source_a.account_balances",
        "source_a/account_balances.csv",
        "balance_count",
        None,
    ),
    (
        "landing_b.received_records",
        "landing_b.csv",
        "total_count",
        "(batch_reference, entity_type, source_record_key, raw_payload)",
    ),
)


def _psql_path() -> str:
    executable = shutil.which("psql")
    if executable is None:
        raise RuntimeError(
            "Could not find psql. Install PostgreSQL client tools and try again."
        )
    return executable


def _connection_environment() -> dict[str, str]:
    environment = os.environ.copy()
    password_file = environment.get("PGPASSFILE")
    default_password_file = Path.home() / ".pgpass"
    has_password_source = (
        bool(environment.get("PGPASSWORD"))
        or bool(environment.get("PGSERVICE"))
        or (
            Path(password_file).is_file()
            if password_file
            else default_password_file.is_file()
        )
    )
    if not has_password_source and sys.stdin.isatty():
        environment["PGPASSWORD"] = getpass.getpass("PostgreSQL password: ")
    return environment


def _run_psql(
    executable: str,
    arguments: list[str],
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [executable, "-X", "-v", "ON_ERROR_STOP=1", *arguments],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"psql failed: {details}")
    return result


def _quote_psql_path(path: Path) -> str:
    return "'" + str(path.resolve()).replace("'", "''") + "'"


def _build_load_script(
    schema_dir: Path,
    data_dir: Path,
    config: GenerationConfig,
    schema_files: tuple[str, ...] = SCHEMA_FILES,
) -> str:
    total_count = (
        config.customer_count
        + config.account_count
        + config.payment_count
        + config.balance_count
    )
    counts = {
        "customer_count": config.customer_count,
        "account_count": config.account_count,
        "payment_count": config.payment_count,
        "balance_count": config.balance_count,
        "total_count": total_count,
    }

    commands = []
    if schema_files:
        commands.append("\\echo 'Creating missing schemas and tables...'")
        commands.extend(
            f"\\i {_quote_psql_path(schema_dir / filename)}"
            for filename in schema_files
        )
    else:
        commands.append("\\echo 'Reusing existing schemas and tables...'")
    commands.append("\\echo 'Loading System A tables and the raw System B batch...'")
    for table, relative_path, count_name, column_list in CSV_LOADS:
        column_clause = f"{column_list} " if column_list else ""
        commands.append(f"\\echo 'Loading {table} ({counts[count_name]} rows)...'")
        commands.append(
            f"\\copy {table} {column_clause}FROM "
            f"{_quote_psql_path(data_dir / relative_path)} "
            "WITH (FORMAT csv, HEADER true)"
        )
    commands.extend(
        (
            "SELECT setval(pg_get_serial_sequence('source_a.customers', 'customer_id'), "
            "COALESCE(MAX(customer_id), 1), MAX(customer_id) IS NOT NULL) "
            "FROM source_a.customers;",
            "SELECT setval(pg_get_serial_sequence('source_a.credit_accounts', "
            "'credit_account_id'), COALESCE(MAX(credit_account_id), 1), "
            "MAX(credit_account_id) IS NOT NULL) FROM source_a.credit_accounts;",
            "SELECT setval(pg_get_serial_sequence('source_a.payments', 'payment_id'), "
            "COALESCE(MAX(payment_id), 1), MAX(payment_id) IS NOT NULL) "
            "FROM source_a.payments;",
            "\\echo 'Verifying loaded row counts...'",
            "SELECT 'source_a.customers' AS target, COUNT(*) AS rows "
            "FROM source_a.customers UNION ALL "
            "SELECT 'source_a.credit_accounts', COUNT(*) "
            "FROM source_a.credit_accounts UNION ALL "
            "SELECT 'source_a.payments', COUNT(*) FROM source_a.payments UNION ALL "
            "SELECT 'source_a.account_balances', COUNT(*) "
            "FROM source_a.account_balances UNION ALL "
            "SELECT 'landing_b.received_records', COUNT(*) "
            "FROM landing_b.received_records;",
            "\\echo 'System B records remain raw and pending in landing_b.'",
        )
    )
    return "\n".join(commands) + "\n"


def _inspect_schemas(
    executable: str, environment: dict[str, str]
) -> dict[str, SchemaState]:
    expected_schemas = ", ".join(
        f"('{schema_name}')" for schema_name in SCHEMA_TABLES
    )
    expected_tables = ", ".join(
        f"('{schema_name}', '{table_name}')"
        for schema_name, table_names in SCHEMA_TABLES.items()
        for table_name in table_names
    )
    expected_columns = ", ".join(
        f"('{schema_name}', '{table_name}', '{column_name}')"
        for schema_name, tables in SCHEMA_COLUMNS.items()
        for table_name, column_names in tables.items()
        for column_name in column_names
    )
    query = f"""
        WITH expected_schemas(schema_name) AS (VALUES {expected_schemas}),
        expected_tables(schema_name, table_name) AS (VALUES {expected_tables}),
        expected_columns(schema_name, table_name, column_name)
            AS (VALUES {expected_columns})
        SELECT COALESCE(
            jsonb_object_agg(
                schemas.schema_name,
                jsonb_build_object(
                    'exists', namespaces.oid IS NOT NULL,
                    'objects_present',
                        EXISTS (
                            SELECT 1
                            FROM pg_class AS objects
                            WHERE objects.relnamespace = namespaces.oid
                              AND objects.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM pg_type AS types
                            WHERE types.typnamespace = namespaces.oid
                              AND types.typtype IN ('e', 'd')
                        ),
                    'missing_tables',
                        COALESCE(
                            (
                                SELECT jsonb_agg(tables.table_name)
                                FROM expected_tables AS tables
                                LEFT JOIN pg_class AS relations
                                    ON relations.relnamespace = namespaces.oid
                                   AND relations.relname = tables.table_name
                                   AND relations.relkind IN ('r', 'p')
                                WHERE tables.schema_name = schemas.schema_name
                                  AND relations.oid IS NULL
                            ),
                            '[]'::jsonb
                        ),
                    'missing_columns',
                        COALESCE(
                            (
                                SELECT jsonb_object_agg(
                                    column_issues.table_name,
                                    column_issues.column_names
                                )
                                FROM (
                                    SELECT expected_column.table_name,
                                           jsonb_agg(expected_column.column_name)
                                               AS column_names
                                    FROM expected_columns AS expected_column
                                    LEFT JOIN information_schema.columns AS actual
                                        ON actual.table_schema =
                                            expected_column.schema_name
                                       AND actual.table_name =
                                            expected_column.table_name
                                       AND actual.column_name =
                                            expected_column.column_name
                                    WHERE expected_column.schema_name =
                                        schemas.schema_name
                                      AND actual.column_name IS NULL
                                    GROUP BY expected_column.table_name
                                ) AS column_issues
                            ),
                            '{{}}'::jsonb
                        )
                )
            ),
            '{{}}'::jsonb
        )::text
        FROM expected_schemas AS schemas
        LEFT JOIN pg_namespace AS namespaces
            ON namespaces.nspname = schemas.schema_name;
    """
    result = _run_psql(
        executable,
        ["--no-align", "--tuples-only", "-c", query],
        environment,
    )
    try:
        schema_state = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Could not read the PostgreSQL schema inspection result."
        ) from error
    if not isinstance(schema_state, dict) or set(schema_state) != set(SCHEMA_TABLES):
        raise RuntimeError("PostgreSQL returned an invalid schema inspection result.")

    validated_state: dict[str, SchemaState] = {}
    for schema_name in SCHEMA_TABLES:
        schema = schema_state[schema_name]
        if (
            not isinstance(schema, dict)
            or not isinstance(schema.get("exists"), bool)
            or not isinstance(schema.get("objects_present"), bool)
            or not isinstance(schema.get("missing_tables"), list)
            or not isinstance(schema.get("missing_columns"), dict)
            or not all(
                isinstance(table_name, str)
                for table_name in schema["missing_tables"]
            )
            or not all(
                isinstance(table_name, str)
                and isinstance(column_names, list)
                and all(isinstance(column_name, str) for column_name in column_names)
                for table_name, column_names in schema["missing_columns"].items()
            )
        ):
            raise RuntimeError(
                "PostgreSQL returned an invalid schema inspection result."
            )
        validated_state[schema_name] = {
            "exists": schema["exists"],
            "objects_present": schema["objects_present"],
            "missing_tables": schema["missing_tables"],
            "missing_columns": schema["missing_columns"],
        }
    return validated_state


def _existing_empty_target_tables(
    executable: str,
    environment: dict[str, str],
    schema_state: dict[str, SchemaState],
) -> None:
    existing_targets = [
        table_name
        for table_name, _, _, _ in CSV_LOADS
        if schema_state[table_name.split(".", maxsplit=1)[0]]["exists"]
        and not schema_state[table_name.split(".", maxsplit=1)[0]]["missing_tables"]
        and not schema_state[table_name.split(".", maxsplit=1)[0]]["missing_columns"]
    ]
    if not existing_targets:
        return

    counts_query = "SELECT jsonb_build_object("
    counts_query += ", ".join(
        f"'{table_name}', (SELECT COUNT(*) FROM {table_name})"
        for table_name in existing_targets
    )
    counts_query += ")::text;"
    result = _run_psql(
        executable,
        ["--no-align", "--tuples-only", "-c", counts_query],
        environment,
    )
    try:
        table_counts = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Could not read the PostgreSQL table counts.") from error
    if not isinstance(table_counts, dict) or not all(
        isinstance(row_count, int) for row_count in table_counts.values()
    ):
        raise RuntimeError("PostgreSQL returned invalid target table counts.")

    populated_tables = {
        table_name: row_count
        for table_name, row_count in table_counts.items()
        if row_count
    }
    if populated_tables:
        details = ", ".join(
            f"{table_name}={row_count}"
            for table_name, row_count in populated_tables.items()
        )
        raise RuntimeError(
            "Refusing to load because target tables already contain data "
            f"({details}). No rows were changed."
        )


def load_into_postgres(
    schema_dir: Path, data_dir: Path, config: GenerationConfig
) -> tuple[str, ...]:
    executable = _psql_path()
    environment = _connection_environment()
    schema_state = _inspect_schemas(executable, environment)
    schema_files_to_create = []
    reused_schemas = []
    for schema_name in SCHEMA_TABLES:
        state = schema_state[schema_name]
        if not state["exists"]:
            schema_files_to_create.append(SCHEMA_FILE_BY_NAME[schema_name])
            continue

        missing_tables = state["missing_tables"]
        missing_columns = state["missing_columns"]
        if not missing_tables and not missing_columns:
            reused_schemas.append(schema_name)
            continue
        if not state["objects_present"]:
            schema_files_to_create.append(SCHEMA_FILE_BY_NAME[schema_name])
            continue

        issues = [
            f"missing tables: {', '.join(missing_tables)}"
        ] if missing_tables else []
        if missing_columns:
            column_details = ", ".join(
                f"{table_name} ({', '.join(column_names)})"
                for table_name, column_names in missing_columns.items()
            )
            issues.append(f"missing columns: {column_details}")
        raise RuntimeError(
            f"Schema {schema_name} exists but is incomplete; "
            f"{'; '.join(issues)}. No rows were changed."
        )

    _existing_empty_target_tables(executable, environment, schema_state)
    if reused_schemas:
        print(f"Reusing existing schemas: {', '.join(reused_schemas)}")
    if schema_files_to_create:
        print(
            "Creating missing or empty schemas: "
            + ", ".join(
                filename.removesuffix(".sql") for filename in schema_files_to_create
            )
        )

    script = _build_load_script(
        schema_dir,
        data_dir,
        config,
        tuple(schema_files_to_create),
    )
    with tempfile.TemporaryDirectory(prefix="data-trust-qa-bootstrap-") as directory:
        script_path = Path(directory) / "bootstrap.sql"
        script_path.write_text(script, encoding="utf-8")
        result = _run_psql(
            executable,
            ["--single-transaction", "--file", str(script_path)],
            environment,
        )

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return tuple(reused_schemas)


def main(argv: list[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[4]
    load_project_environment(project_root)
    defaults = GenerationConfig()
    parser = argparse.ArgumentParser(
        description=(
            "Generate a synthetic dataset and optionally bootstrap it into "
            "PostgreSQL without overwriting existing target data."
        )
    )
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--customers", type=int, default=defaults.customer_count)
    parser.add_argument("--accounts", type=int, default=defaults.account_count)
    parser.add_argument("--payments", type=int, default=defaults.payment_count)
    parser.add_argument("--balances", type=int, default=defaults.balance_count)
    parser.add_argument("--batch-reference", default="BATCH-0001")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "data" / "generated",
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=project_root / "database" / "schemas",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help=(
            "Create missing schemas and load into empty target tables; "
            "reuse complete existing schemas."
        ),
    )
    args = parser.parse_args(argv)

    try:
        config = GenerationConfig(
            seed=args.seed,
            customer_count=args.customers,
            account_count=args.accounts,
            payment_count=args.payments,
            balance_count=args.balances,
        )
    except ValueError as error:
        parser.error(str(error))

    output_dir = args.output_dir / f"seed-{config.seed}"
    dataset = generate_dataset(config)
    write_dataset(dataset, output_dir, args.batch_reference)
    total_count = (
        config.customer_count
        + config.account_count
        + config.payment_count
        + config.balance_count
    )

    print("Bootstrap plan")
    print(f"  Seed: {config.seed}")
    print(f"  Batch: {args.batch_reference}")
    print(f"  Rows per system: {total_count:,}")
    print(
        "  Entities: "
        f"customers={config.customer_count:,}, "
        f"credit_accounts={config.account_count:,}, "
        f"payments={config.payment_count:,}, "
        f"account_balances={config.balance_count:,}"
    )
    print(f"  Generated files: {output_dir}")
    print("  PostgreSQL targets: source_a and landing_b; source_b stays empty.")

    if not args.load:
        print("  Database unchanged. Pass --load to create and load the schemas.")
        return 0

    try:
        load_into_postgres(args.schema_dir, output_dir, config)
    except RuntimeError as error:
        parser.error(str(error))

    print("Bootstrap completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
