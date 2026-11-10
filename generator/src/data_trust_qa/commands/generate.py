import argparse
from pathlib import Path

from ..config.environment import load_project_environment
from ..domain.models import GenerationConfig
from ..generation.dataset import generate_dataset
from ..generation.exporters import write_dataset


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    project_root = _project_root()
    load_project_environment(project_root)
    defaults = GenerationConfig()
    parser = argparse.ArgumentParser(
        description="Generate a reproducible synthetic A dataset and B landing batch."
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

    dataset = generate_dataset(config)
    output_dir = args.output_dir / f"seed-{config.seed}"
    write_dataset(dataset, output_dir, args.batch_reference)

    print(f"Generated sample: {output_dir}")
    print(
        "Rows: "
        f"customers={len(dataset.customers)}, "
        f"credit_accounts={len(dataset.credit_accounts)}, "
        f"payments={len(dataset.payments)}, "
        f"account_balances={len(dataset.account_balances)}"
    )
    print("System A: CSV tables; System B: raw landing batch.")
    return 0
