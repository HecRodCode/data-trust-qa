import argparse
import tempfile
from pathlib import Path

from ..config.environment import load_project_environment
from .bootstrap import (
    _connection_environment,
    _inspect_schemas,
    _psql_path,
    _run_psql,
)


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_process_script(batch_reference: str) -> str:
    batch = _quote_sql_literal(batch_reference)
    return f"""
LOCK TABLE
    source_b.customers,
    source_b.credit_accounts,
    source_b.payments,
    source_b.account_balances,
    landing_b.received_records
IN SHARE ROW EXCLUSIVE MODE;

DO $process_batch$
DECLARE
    batch_total BIGINT;
    batch_pending BIGINT;
    target_rows BIGINT;
BEGIN
    SELECT COUNT(*),
           COUNT(*) FILTER (WHERE processing_status = 'pendiente')
      INTO batch_total, batch_pending
      FROM landing_b.received_records
     WHERE batch_reference = {batch};

    IF batch_total = 0 THEN
        RAISE EXCEPTION 'No records found for batch %', {batch};
    END IF;

    IF batch_pending <> batch_total THEN
        RAISE EXCEPTION
            'Batch % has % pending records out of %; expected all records pending',
            {batch}, batch_pending, batch_total;
    END IF;

    SELECT COUNT(*) INTO target_rows FROM source_b.customers;
    IF target_rows <> 0 THEN
        RAISE EXCEPTION
            'source_b is not empty; refusing to process a batch over existing data';
    END IF;

    SELECT COUNT(*) INTO target_rows FROM source_b.credit_accounts;
    IF target_rows <> 0 THEN
        RAISE EXCEPTION 'source_b.credit_accounts is not empty';
    END IF;
    SELECT COUNT(*) INTO target_rows FROM source_b.payments;
    IF target_rows <> 0 THEN
        RAISE EXCEPTION 'source_b.payments is not empty';
    END IF;
    SELECT COUNT(*) INTO target_rows FROM source_b.account_balances;
    IF target_rows <> 0 THEN
        RAISE EXCEPTION 'source_b.account_balances is not empty';
    END IF;
END
$process_batch$;

\\echo 'Processing customers...'
INSERT INTO source_b.customers (document_type, document_number)
SELECT raw_payload ->> 'document_type',
       raw_payload ->> 'document_number'
  FROM landing_b.received_records
 WHERE batch_reference = {batch}
   AND entity_type = 'customers'
   AND processing_status = 'pendiente'
 ORDER BY received_record_id;

\\echo 'Processing credit accounts...'
INSERT INTO source_b.credit_accounts (
    account_business_key,
    customer_id,
    product_type,
    opening_date,
    account_status
)
SELECT payload.raw_payload ->> 'account_business_key',
       customers.customer_id,
       payload.raw_payload ->> 'product_type',
       (payload.raw_payload ->> 'opening_date')::DATE,
       (payload.raw_payload ->> 'account_status')::source_b.account_status_type
  FROM landing_b.received_records AS payload
  LEFT JOIN source_b.customers AS customers
    ON customers.document_type =
        payload.raw_payload ->> 'customer_document_type'
   AND customers.document_number =
        payload.raw_payload ->> 'customer_document_number'
 WHERE payload.batch_reference = {batch}
   AND payload.entity_type = 'credit_accounts'
   AND payload.processing_status = 'pendiente'
 ORDER BY payload.received_record_id;

\\echo 'Processing payments...'
INSERT INTO source_b.payments (
    payment_business_key,
    credit_account_id,
    payment_date,
    payment_amount,
    payment_status
)
SELECT payload.raw_payload ->> 'payment_business_key',
       accounts.credit_account_id,
       (payload.raw_payload ->> 'payment_date')::DATE,
       (payload.raw_payload ->> 'payment_amount')::NUMERIC(15, 2),
       (payload.raw_payload ->> 'payment_status')::source_b.payment_status_type
  FROM landing_b.received_records AS payload
  LEFT JOIN source_b.credit_accounts AS accounts
    ON accounts.account_business_key =
        payload.raw_payload ->> 'account_business_key'
 WHERE payload.batch_reference = {batch}
   AND payload.entity_type = 'payments'
   AND payload.processing_status = 'pendiente'
 ORDER BY payload.received_record_id;

\\echo 'Processing account balances...'
INSERT INTO source_b.account_balances (
    credit_account_id,
    cutoff_date,
    principal_balance,
    interest_balance,
    fees_balance,
    total_balance,
    currency
)
SELECT accounts.credit_account_id,
       (payload.raw_payload ->> 'cutoff_date')::DATE,
       (payload.raw_payload ->> 'principal_balance')::NUMERIC(15, 2),
       (payload.raw_payload ->> 'interest_balance')::NUMERIC(15, 2),
       (payload.raw_payload ->> 'fees_balance')::NUMERIC(15, 2),
       (payload.raw_payload ->> 'total_balance')::NUMERIC(15, 2),
       payload.raw_payload ->> 'currency'
  FROM landing_b.received_records AS payload
  LEFT JOIN source_b.credit_accounts AS accounts
    ON accounts.account_business_key =
        payload.raw_payload ->> 'account_business_key'
 WHERE payload.batch_reference = {batch}
   AND payload.entity_type = 'account_balances'
   AND payload.processing_status = 'pendiente'
 ORDER BY payload.received_record_id;

DO $verify_batch$
DECLARE
    mismatch TEXT;
BEGIN
    SELECT string_agg(expected.entity_type, ', ')
      INTO mismatch
      FROM (
          SELECT 'customers' AS entity_type,
                 COUNT(*) FILTER (
                     WHERE entity_type = 'customers'
                 ) AS expected_rows,
                 (SELECT COUNT(*) FROM source_b.customers) AS actual_rows
            FROM landing_b.received_records
           WHERE batch_reference = {batch}
          UNION ALL
          SELECT 'credit_accounts',
                 COUNT(*) FILTER (
                     WHERE entity_type = 'credit_accounts'
                 ),
                 (SELECT COUNT(*) FROM source_b.credit_accounts)
            FROM landing_b.received_records
           WHERE batch_reference = {batch}
          UNION ALL
          SELECT 'payments',
                 COUNT(*) FILTER (
                     WHERE entity_type = 'payments'
                 ),
                 (SELECT COUNT(*) FROM source_b.payments)
            FROM landing_b.received_records
           WHERE batch_reference = {batch}
          UNION ALL
          SELECT 'account_balances',
                 COUNT(*) FILTER (
                     WHERE entity_type = 'account_balances'
                 ),
                 (SELECT COUNT(*) FROM source_b.account_balances)
            FROM landing_b.received_records
           WHERE batch_reference = {batch}
      ) AS expected
     WHERE expected.expected_rows <> expected.actual_rows;

    IF mismatch IS NOT NULL THEN
        RAISE EXCEPTION
            'Processed row counts do not match landing batch for: %',
            mismatch;
    END IF;
END
$verify_batch$;

UPDATE landing_b.received_records
   SET processing_status = 'aceptado',
       validation_errors = '[]'::JSONB
 WHERE batch_reference = {batch}
   AND processing_status = 'pendiente';

\\echo 'Verifying processed row counts...'
SELECT 'source_b.customers' AS target, COUNT(*) AS rows
  FROM source_b.customers
UNION ALL
SELECT 'source_b.credit_accounts', COUNT(*)
  FROM source_b.credit_accounts
UNION ALL
SELECT 'source_b.payments', COUNT(*)
  FROM source_b.payments
UNION ALL
SELECT 'source_b.account_balances', COUNT(*)
  FROM source_b.account_balances
UNION ALL
SELECT 'landing_b accepted batch records', COUNT(*)
  FROM landing_b.received_records
 WHERE batch_reference = {batch}
   AND processing_status = 'aceptado';
"""


def process_batch(batch_reference: str) -> None:
    executable = _psql_path()
    environment = _connection_environment()
    schema_state = _inspect_schemas(executable, environment)

    for schema_name in ("source_b", "landing_b"):
        state = schema_state[schema_name]
        if not state["exists"]:
            raise RuntimeError(f"Required schema {schema_name} does not exist.")
        if state["missing_tables"] or state["missing_columns"]:
            raise RuntimeError(
                f"Required schema {schema_name} is incomplete. "
                "Check its schema against the project SQL files."
            )

    script = _build_process_script(batch_reference)
    with tempfile.TemporaryDirectory(
        prefix="data-trust-qa-process-"
    ) as temporary_directory:
        script_path = Path(temporary_directory) / "process_batch.sql"
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


def main(argv: list[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[4]
    load_project_environment(project_root)
    parser = argparse.ArgumentParser(
        description="Process a pending System B landing batch into source_b."
    )
    parser.add_argument("--batch-reference", default="BATCH-0001")
    args = parser.parse_args(argv)

    try:
        process_batch(args.batch_reference)
    except RuntimeError as error:
        parser.error(str(error))

    print(f"Batch {args.batch_reference} processed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
