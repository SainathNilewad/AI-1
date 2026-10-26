"""
Configuration loader utility.
Loads and validates domain and pricing YAML configurations.
All paths are resolved relative to the project root to prevent working-directory bugs.
"""

from pathlib import Path
from typing import Any, Dict
import yaml

# Resolve project root as the parent of this file's directory (src/ -> project_root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"


def load_yaml(file_path: Path | str) -> Dict[str, Any]:
    """
    Safely load a YAML file into a Python dictionary.

    Args:
        file_path: Absolute or project-root-relative path to the YAML file.

    Returns:
        Dict containing the parsed YAML data.

    Raises:
        FileNotFoundError: If the specified configuration file does not exist.
        ValueError: If the file is empty or does not contain a valid mapping.
        yaml.YAMLError: If parsing fails due to invalid YAML syntax.
    """
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


def load_domain_config(domain: str = "real_estate") -> Dict[str, Any]:
    """
    Load a domain-specific YAML configuration (e.g., real_estate.yaml, jobs.yaml).

    Args:
        domain: Domain name matching the filename prefix in configs/<domain>.yaml.

    Returns:
        Dict containing schema rules, aliases, units, and prompts.
    """
    config_path = CONFIGS_DIR / f"{domain}.yaml"
    return load_yaml(config_path)


def load_pricing_config() -> Dict[str, Any]:
    """
    Load dated model pricing configuration from configs/prices.yaml.

    Returns:
        Dict containing dated pricing per 1M tokens by model name.
    """
    config_path = CONFIGS_DIR / "prices.yaml"
    return load_yaml(config_path)
