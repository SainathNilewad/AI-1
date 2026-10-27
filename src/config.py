from pathlib import Path
from typing import Any
import yaml

# Anchor to project root so paths resolve identically across tests and CLI runs
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"


def load_yaml(file_path: Path | str) -> dict[str, Any]:
    """Load and validate a YAML file, resolving relative paths from project root."""
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Configuration file is empty: {path}")

    if not isinstance(data, dict):
        raise ValueError(f"Configuration file root must be a mapping/dict: {path}")

    return data


def load_domain_config(domain: str = "real_estate") -> dict[str, Any]:
    """Load domain schema and extraction rules from configs/<domain>.yaml."""
    return load_yaml(CONFIGS_DIR / f"{domain}.yaml")


def load_pricing_config() -> dict[str, Any]:
    """Load model token pricing table from configs/prices.yaml."""
    return load_yaml(CONFIGS_DIR / "prices.yaml")
