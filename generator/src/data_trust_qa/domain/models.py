"""Domain models shared by generation and database workflows."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    seed: int = 20261110
    customer_count: int = 4_000
    account_count: int = 6_000
    payment_count: int = 12_000
    balance_count: int = 3_000

    def __post_init__(self) -> None:
        counts = {
            "customer_count": self.customer_count,
            "account_count": self.account_count,
            "payment_count": self.payment_count,
            "balance_count": self.balance_count,
        }
        for name, value in counts.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")

        if self.account_count and not self.customer_count:
            raise ValueError("Accounts require at least one customer")
        if (self.payment_count or self.balance_count) and not self.account_count:
            raise ValueError("Payments and balances require at least one account")


@dataclass(frozen=True, slots=True)
class Customer:
    customer_id: int
    document_type: str
    document_number: str


@dataclass(frozen=True, slots=True)
class CreditAccount:
    credit_account_id: int
    account_business_key: str
    customer_id: int
    product_type: str
    opening_date: date
    account_status: str


@dataclass(frozen=True, slots=True)
class Payment:
    payment_id: int
    payment_business_key: str
    credit_account_id: int
    payment_date: date
    payment_amount: str
    payment_status: str


@dataclass(frozen=True, slots=True)
class AccountBalance:
    credit_account_id: int
    cutoff_date: date
    principal_balance: str
    interest_balance: str
    fees_balance: str
    total_balance: str
    currency: str


@dataclass(frozen=True, slots=True)
class Dataset:
    customers: tuple[Customer, ...]
    credit_accounts: tuple[CreditAccount, ...]
    payments: tuple[Payment, ...]
    account_balances: tuple[AccountBalance, ...]
