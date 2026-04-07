"""Config file support for deterministic re-generation.

Loads and saves ``.bootstrap-iac.yaml`` files so teams can commit their
interview answers and re-generate consistently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


# Config file names to auto-detect (in priority order)
CONFIG_FILENAMES = [".bootstrap-iac.yaml", ".bootstrap-iac.yml"]

# Mapping from config file keys to CLI override keys (UPPER_CASE)
_KEY_MAP: dict[str, str] = {
    "company": "COMPANY_NAME",
    "cloud": "CLOUD_PROVIDER",
    "module_prefix": "MODULE_PREFIX",
    "orchestration": "ORCHESTRATION_TOOL",
    "orchestration_dir": "ORCHESTRATION_DIR",
    "ci_cd": "CI_CD_PLATFORM",
    "auth": "AUTH_PATTERN",
    "state_backend": "STATE_BACKEND",
    "naming": "NAMING_PATTERN",
    "tag_strategy": "TAG_STRATEGY",
    "org": "ORG",
    "target": "TARGET",
}

# Reverse mapping for save_config
_REVERSE_KEY_MAP: dict[str, str] = {v: k for k, v in _KEY_MAP.items()}

# Values that need normalisation from CLI lowercase to interview title-case
_CLOUD_MAP: dict[str, str] = {"azure": "Azure", "aws": "AWS", "gcp": "GCP"}
_ORCH_MAP: dict[str, str] = {
    "terragrunt": "Terragrunt",
    "terramate": "Terramate",
    "pulumi": "Pulumi",
    "none": "None",
}
_CICD_MAP: dict[str, str] = {
    "github-actions": "GitHub Actions",
    "azure-devops": "Azure DevOps",
    "gitlab-ci": "GitLab CI",
    "atlantis": "Atlantis",
}


def find_config(workspace: Path) -> Optional[Path]:
    """Return the first config file found in *workspace*, or ``None``."""
    for name in CONFIG_FILENAMES:
        path = workspace / name
        if path.is_file():
            return path
    return None


def load_config(path: Path) -> dict[str, str]:
    """Load a config file and return normalised overrides (UPPER_CASE keys).

    Values are normalised to match what ``run_interview`` expects
    (e.g. ``"azure"`` → ``"Azure"``).
    """
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(raw).__name__}")

    overrides: dict[str, str] = {}
    for file_key, value in raw.items():
        upper_key = _KEY_MAP.get(file_key)
        if upper_key is None:
            continue  # ignore unknown keys
        str_val = str(value)

        # Normalise known enum values
        if upper_key == "CLOUD_PROVIDER":
            str_val = _CLOUD_MAP.get(str_val.lower(), str_val)
        elif upper_key == "ORCHESTRATION_TOOL":
            str_val = _ORCH_MAP.get(str_val.lower(), str_val)
        elif upper_key == "CI_CD_PLATFORM":
            str_val = _CICD_MAP.get(str_val.lower(), str_val)

        overrides[upper_key] = str_val

    return overrides


def save_config(answers: dict[str, str], path: Path) -> None:
    """Write interview answers to a YAML config file."""
    config: dict[str, str] = {}
    for upper_key, file_key in sorted(_REVERSE_KEY_MAP.items(), key=lambda x: x[1]):
        value = answers.get(upper_key)
        if value:
            config[file_key] = value

    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False, sort_keys=True, allow_unicode=True)
