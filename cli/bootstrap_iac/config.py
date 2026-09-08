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

# Config schema version. write_config stamps this; load_config accepts it.
# A config with no version is treated as the current version.
CONFIG_VERSION = "1"
SUPPORTED_CONFIG_VERSIONS = {"1", "1.0"}

# The config-file key that carries the schema version (meta, not a placeholder).
_VERSION_KEY = "version"

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
    "standard_variables": "STANDARD_VARIABLES",
    "org": "ORG",
    "target": "TARGET",
}

# Reverse mapping for write_config
_REVERSE_KEY_MAP: dict[str, str] = {v: k for k, v in _KEY_MAP.items()}

# Every recognised config-file key: the mapped placeholder keys plus meta keys.
KNOWN_KEYS: frozenset[str] = frozenset(_KEY_MAP) | {_VERSION_KEY}


def config_key_for(upper_key: str) -> str:
    """Return the config-file key that maps to the placeholder *upper_key*.

    Falls back to *upper_key* itself when there is no mapping.
    """
    return _REVERSE_KEY_MAP.get(upper_key, upper_key)

# Values that need normalisation from CLI lowercase to interview title-case
CLOUD_MAP: dict[str, str] = {"azure": "Azure", "aws": "AWS", "gcp": "GCP"}
ORCH_MAP: dict[str, str] = {
    "terragrunt": "Terragrunt",
    "terramate": "Terramate",
    "pulumi": "Pulumi",
    "none": "None",
}
CICD_MAP: dict[str, str] = {
    "github-actions": "GitHub Actions",
    "azure-devops": "Azure DevOps",
    "gitlab-ci": "GitLab CI",
    "atlantis": "Atlantis",
}


def _build_lookup(mapping: dict[str, str]) -> dict[str, str]:
    """Build a case-insensitive lookup accepting both slug keys and display values."""
    lookup: dict[str, str] = {}
    for slug, display in mapping.items():
        lookup[slug.lower()] = display
        lookup[display.lower()] = display
    return lookup


_CLOUD_LOOKUP = _build_lookup(CLOUD_MAP)
_ORCH_LOOKUP = _build_lookup(ORCH_MAP)
_CICD_LOOKUP = _build_lookup(CICD_MAP)


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

    # Reject unknown keys so a typo (for example `clould:`) fails loudly instead
    # of silently producing incomplete output.
    unknown_keys = [str(key) for key in raw if key not in KNOWN_KEYS]
    if unknown_keys:
        supported = ", ".join(sorted(KNOWN_KEYS))
        raise ValueError(
            "Unknown config key(s): "
            + ", ".join(f"'{key}'" for key in unknown_keys)
            + f". Supported keys: {supported}."
        )

    # Validate the optional schema version. A YAML null means "unset" (use the
    # current version), but an explicitly provided empty/whitespace value is a
    # mistake and is rejected.
    version_raw = raw.get(_VERSION_KEY)
    if version_raw is not None:
        version_val = str(version_raw).strip()
        if version_val not in SUPPORTED_CONFIG_VERSIONS:
            raise ValueError(
                f"Config key '{_VERSION_KEY}' has unsupported value '{version_val}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_CONFIG_VERSIONS))}"
            )

    overrides: dict[str, str] = {}
    for file_key, value in raw.items():
        if file_key == _VERSION_KEY:
            continue  # meta key, not a placeholder override

        upper_key = _KEY_MAP.get(file_key)
        if upper_key is None:
            continue  # unreachable: unknown keys already rejected above

        if value is None:
            continue  # treat YAML null as unset

        if isinstance(value, str):
            str_val = value.strip()
            if not str_val:
                continue  # treat empty/whitespace-only strings as unset
        elif isinstance(value, (bool, int, float)):
            str_val = str(value)
        else:
            raise ValueError(
                f"Config key '{file_key}' must be a YAML scalar, got {type(value).__name__}"
            )

        # Normalise and validate known enum values
        if upper_key == "CLOUD_PROVIDER":
            normalised = _CLOUD_LOOKUP.get(str_val.lower())
            if normalised is None:
                raise ValueError(
                    f"Config key 'cloud' has unsupported value '{str_val}'. "
                    f"Supported: {', '.join(CLOUD_MAP)}"
                )
            str_val = normalised
        elif upper_key == "ORCHESTRATION_TOOL":
            normalised = _ORCH_LOOKUP.get(str_val.lower())
            if normalised is None:
                raise ValueError(
                    f"Config key 'orchestration' has unsupported value '{str_val}'. "
                    f"Supported: {', '.join(ORCH_MAP)}"
                )
            str_val = normalised
        elif upper_key == "CI_CD_PLATFORM":
            normalised = _CICD_LOOKUP.get(str_val.lower())
            if normalised is None:
                raise ValueError(
                    f"Config key 'ci_cd' has unsupported value '{str_val}'. "
                    f"Supported: {', '.join(CICD_MAP)}"
                )
            str_val = normalised
        elif upper_key == "TARGET":
            lower = str_val.lower()
            if lower not in ("copilot", "claude", "both"):
                raise ValueError(
                    f"Config key 'target' has unsupported value '{str_val}'. "
                    f"Supported: copilot, claude, both"
                )
            str_val = lower

        overrides[upper_key] = str_val

    return overrides


def write_config(answers: dict[str, str], path: Path) -> None:
    """Write interview answers to a YAML config file.

    The file is stamped with the current schema :data:`CONFIG_VERSION` so it can
    be validated and migrated later.
    """
    config: dict[str, str] = {_VERSION_KEY: CONFIG_VERSION}
    for upper_key, file_key in sorted(_REVERSE_KEY_MAP.items(), key=lambda x: x[1]):
        value = answers.get(upper_key)
        if value:
            config[file_key] = value

    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
