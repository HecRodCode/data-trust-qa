"""Load local project settings from the root environment file."""

from pathlib import Path

from dotenv import load_dotenv


def load_project_environment(project_root: Path) -> None:
    load_dotenv(project_root / ".env", override=False)
