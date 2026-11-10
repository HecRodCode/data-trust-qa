import csv
import json
from dataclasses import asdict, fields
from datetime import date
from pathlib import Path
from typing import Iterable

from ..domain.models import AccountBalance, CreditAccount, Customer, Dataset, Payment

CsvRow = Customer | CreditAccount | Payment | AccountBalance


def _csv_value(value: object) -> object:
    return value.isoformat() if isinstance(value, date) else value


def _write_csv(path: Path, row_type: type[CsvRow], rows: Iterable[CsvRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(row_type)]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {name: _csv_value(value) for name, value in asdict(row).items()}
            )


def _landing_record(
    batch_reference: str,
    entity_type: str,
    source_record_key: str,
    payload: dict[str, str],
) -> dict[str, str]:
    return {
        "batch_reference": batch_reference,
        "entity_type": entity_type,
        "source_record_key": source_record_key,
        "raw_payload": json.dumps(payload, sort_keys=True),
    }


def write_dataset(
    dataset: Dataset, output_dir: Path, batch_reference: str
) -> None:
    source_a_dir = output_dir / "source_a"
    _write_csv(source_a_dir / "customers.csv", Customer, dataset.customers)
    _write_csv(
        source_a_dir / "credit_accounts.csv",
        CreditAccount,
        dataset.credit_accounts,
    )
    _write_csv(source_a_dir / "payments.csv", Payment, dataset.payments)
    _write_csv(
        source_a_dir / "account_balances.csv",
        AccountBalance,
        dataset.account_balances,
    )

    accounts_by_id = {
        account.credit_account_id: account for account in dataset.credit_accounts
    }
    customers_by_id = {customer.customer_id: customer for customer in dataset.customers}
    landing_records: list[dict[str, str]] = []

    for customer in dataset.customers:
        key = f"{customer.document_type}:{customer.document_number}"
        landing_records.append(
            _landing_record(
                batch_reference,
                "customers",
                key,
                {
                    "document_type": customer.document_type,
                    "document_number": customer.document_number,
                },
            )
        )

    for account in dataset.credit_accounts:
        customer = customers_by_id[account.customer_id]
        landing_records.append(
            _landing_record(
                batch_reference,
                "credit_accounts",
                account.account_business_key,
                {
                    "account_business_key": account.account_business_key,
                    "customer_document_type": customer.document_type,
                    "customer_document_number": customer.document_number,
                    "product_type": account.product_type,
                    "opening_date": account.opening_date.isoformat(),
                    "account_status": account.account_status,
                },
            )
        )

    for payment in dataset.payments:
        account = accounts_by_id[payment.credit_account_id]
        landing_records.append(
            _landing_record(
                batch_reference,
                "payments",
                payment.payment_business_key,
                {
                    "payment_business_key": payment.payment_business_key,
                    "account_business_key": account.account_business_key,
                    "payment_date": payment.payment_date.isoformat(),
                    "payment_amount": payment.payment_amount,
                    "payment_status": payment.payment_status,
                },
            )
        )

    for balance in dataset.account_balances:
        account = accounts_by_id[balance.credit_account_id]
        cutoff_date = balance.cutoff_date.isoformat()
        landing_records.append(
            _landing_record(
                batch_reference,
                "account_balances",
                f"{account.account_business_key}:{cutoff_date}",
                {
                    "account_business_key": account.account_business_key,
                    "cutoff_date": cutoff_date,
                    "principal_balance": balance.principal_balance,
                    "interest_balance": balance.interest_balance,
                    "fees_balance": balance.fees_balance,
                    "total_balance": balance.total_balance,
                    "currency": balance.currency,
                },
            )
        )

    landing_path = output_dir / "landing_b.csv"
    landing_path.parent.mkdir(parents=True, exist_ok=True)
    with landing_path.open("w", newline="", encoding="utf-8") as file:
        fieldnames: list[str] = [
            "batch_reference",
            "entity_type",
            "source_record_key",
            "raw_payload",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(landing_records)
