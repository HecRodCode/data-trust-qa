import random
from datetime import date, timedelta

from ..domain.models import (
    AccountBalance,
    CreditAccount,
    Customer,
    Dataset,
    GenerationConfig,
    Payment,
)

ACCOUNT_STATUSES = ("activo", "inactivo", "bloqueado", "cancelado")
PAYMENT_STATUSES = ("pendiente", "aplicado", "rechazado", "reversado")


def _format_amount(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def generate_dataset(config: GenerationConfig) -> Dataset:
    rng = random.Random(config.seed)

    customers = tuple(
        Customer(
            customer_id=index,
            document_type="SYN",
            document_number=f"SYN-{index:08d}",
        )
        for index in range(1, config.customer_count + 1)
    )

    account_rows = []
    for index in range(1, config.account_count + 1):
        account_rows.append(
            CreditAccount(
                credit_account_id=index,
                account_business_key=f"ACC-{index:08d}",
                customer_id=rng.choice(customers).customer_id,
                product_type="synthetic_credit",
                opening_date=date(2023, 1, 1) + timedelta(days=rng.randrange(365)),
                account_status=rng.choice(ACCOUNT_STATUSES),
            )
        )
    accounts = tuple(account_rows)

    payment_rows = []
    for index in range(1, config.payment_count + 1):
        account = rng.choice(accounts)
        payment_rows.append(
            Payment(
                payment_id=index,
                payment_business_key=f"PAY-{index:08d}",
                credit_account_id=account.credit_account_id,
                payment_date=account.opening_date
                + timedelta(days=rng.randrange(1, 731)),
                payment_amount=_format_amount(rng.randint(100, 500_000)),
                payment_status=rng.choice(PAYMENT_STATUSES),
            )
        )
    payments = tuple(payment_rows)

    balance_rows = []
    for index in range(config.balance_count):
        account = accounts[index % len(accounts)]
        principal_cents = rng.randint(0, 5_000_000)
        interest_cents = rng.randint(0, 500_000)
        fees_cents = rng.randint(0, 100_000)
        balance_rows.append(
            AccountBalance(
                credit_account_id=account.credit_account_id,
                cutoff_date=date(2025, 1, 1)
                + timedelta(days=index // len(accounts)),
                principal_balance=_format_amount(principal_cents),
                interest_balance=_format_amount(interest_cents),
                fees_balance=_format_amount(fees_cents),
                total_balance=_format_amount(
                    principal_cents + interest_cents + fees_cents
                ),
                currency="USD",
            )
        )
    balances = tuple(balance_rows)

    return Dataset(
        customers=customers,
        credit_accounts=accounts,
        payments=payments,
        account_balances=balances,
    )
