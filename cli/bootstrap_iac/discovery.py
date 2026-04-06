"""Workspace auto-detection: scan an IaC workspace to infer defaults."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DiscoveryResult:
    """Results of a workspace scan used to seed interview defaults."""

    workspace_path: Path

    # Cloud provider detected from provider blocks in .tf files
    cloud_provider: Optional[str] = None  # "Azure" | "AWS" | "GCP"

    # Module directory prefix (e.g. "tf-module", "terraform-aws")
    module_prefix: Optional[str] = None

    # Organisation name guessed from git remote URL
    org_name: Optional[str] = None

    # Orchestration tool detected from config files
    orchestration_tool: Optional[str] = None  # "Terragrunt" | "Terramate" | "Pulumi" | "None"

    # Directory that holds orchestration config files
    orchestration_dir: Optional[str] = None

    # CI/CD platform inferred from pipeline file locations
    ci_cd_platform: Optional[str] = None

    # Directory where pipeline files live
    pipeline_dir: Optional[str] = None

    # Terraform state backend (e.g. "Azure Blob Storage", "S3", "GCS")
    state_backend: Optional[str] = None

    # Naming pattern inferred from resource name expressions
    naming_pattern: Optional[str] = None

    # Whether a .github/copilot-instructions.md already exists
    has_copilot_instructions: bool = False

    # Whether a CLAUDE.md already exists
    has_claude_md: bool = False

    # Any extra notes discovered (shown as hints in the interview)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PROVIDER_PATTERNS = {
    "Azure": re.compile(r'provider\s+"azurerm"', re.IGNORECASE),
    "AWS": re.compile(r'provider\s+"aws"', re.IGNORECASE),
    "GCP": re.compile(r'provider\s+"google"', re.IGNORECASE),
}

_PROVIDER_REQUIRED_PATTERNS = {
    "Azure": re.compile(r'"azurerm"\s*=\s*\{', re.IGNORECASE),
    "AWS": re.compile(r'"aws"\s*=\s*\{', re.IGNORECASE),
    "GCP": re.compile(r'"google"\s*=\s*\{', re.IGNORECASE),
}


def _detect_cloud_provider(workspace: Path) -> Optional[str]:
    """Return detected cloud provider from .tf files, or None."""
    counts: dict[str, int] = {"Azure": 0, "AWS": 0, "GCP": 0}
    for tf_file in workspace.rglob("*.tf"):
        if ".terraform" in tf_file.parts:
            continue
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for provider, pattern in _PROVIDER_PATTERNS.items():
            if pattern.search(content):
                counts[provider] += 1
        for provider, pattern in _PROVIDER_REQUIRED_PATTERNS.items():
            if pattern.search(content):
                counts[provider] += 1
    if not any(counts.values()):
        return None
    return max(counts, key=lambda k: counts[k])


def _detect_module_prefix(workspace: Path) -> Optional[str]:
    """Guess module prefix from directory names like tf-module-*, terraform-aws-*, modules/."""
    candidates: list[str] = []
    for entry in workspace.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        for pattern in (
            r"^(tf-module)-",
            r"^(terraform-[a-z]+-[a-z]+)-",
            r"^(terraform-[a-z]+)-",
            r"^(tf-[a-z]+)-",
        ):
            m = re.match(pattern, name)
            if m:
                candidates.append(m.group(1))
                break
    if candidates:
        # Return the most common prefix
        return Counter(candidates).most_common(1)[0][0]
    # Check for a generic "modules/" directory
    if (workspace / "modules").is_dir():
        return "modules"
    return None


def _detect_orchestration(workspace: Path) -> tuple[Optional[str], Optional[str]]:
    """Return (tool_name, dir_name) or (None, None).

    Heuristics:
    - Terragrunt: any ``terragrunt.hcl`` file (outside .terraform/)
    - Terramate: any ``terramate.tm.hcl`` file
    - Pulumi: a ``Pulumi.yaml`` file
    """
    for hcl_file in workspace.rglob("terragrunt.hcl"):
        if ".terraform" in hcl_file.parts:
            continue
        rel = hcl_file.parent.relative_to(workspace)
        parts = rel.parts
        orch_dir = parts[0] if parts else "."
        return "Terragrunt", orch_dir
    for hcl_file in workspace.rglob("terramate.tm.hcl"):
        if ".terraform" in hcl_file.parts:
            continue
        rel = hcl_file.parent.relative_to(workspace)
        parts = rel.parts
        orch_dir = parts[0] if parts else "."
        return "Terramate", orch_dir
    for yaml_file in workspace.rglob("Pulumi.yaml"):
        rel = yaml_file.parent.relative_to(workspace)
        parts = rel.parts
        orch_dir = parts[0] if parts else "."
        return "Pulumi", orch_dir
    return None, None


def _detect_ci_cd(workspace: Path) -> tuple[Optional[str], Optional[str]]:
    """Return (platform_name, pipeline_dir) or (None, None)."""
    if (workspace / ".github" / "workflows").is_dir():
        return "GitHub Actions", ".github/workflows"
    if (workspace / "azure-pipelines.yml").exists():
        return "Azure DevOps", "."
    for yml_file in workspace.rglob("azure-pipelines*.yml"):
        rel = str(yml_file.parent.relative_to(workspace))
        return "Azure DevOps", rel
    if (workspace / ".gitlab-ci.yml").exists():
        return "GitLab CI", "."
    for yml_file in workspace.glob("**/pipelines/**/*.yml"):
        rel = str(yml_file.parent.relative_to(workspace))
        return "Unknown", rel
    return None, None


def _detect_org_from_git(workspace: Path) -> Optional[str]:
    """Try to extract organisation name from git remote URL.

    Heuristic: parse ``.git/config`` for a remote URL and extract the
    organisation segment from ``github.com/ORG/REPO`` or ``git@...:ORG/REPO``.
    Walks up parent directories to find a git root if needed.
    """
    git_config = workspace / ".git" / "config"
    if not git_config.exists():
        # Walk up to find a git root
        for parent in workspace.parents:
            if (parent / ".git" / "config").exists():
                git_config = parent / ".git" / "config"
                break
        else:
            return None
    try:
        content = git_config.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    # Match: url = https://github.com/ORG/REPO or git@github.com:ORG/REPO
    m = re.search(r"url\s*=\s*.*[:/]([^/\s]+)/[^/\s]+(?:\.git)?", content)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# State backend & naming pattern detection
# ---------------------------------------------------------------------------

_BACKEND_PATTERNS = {
    "Azure Blob Storage": re.compile(r'backend\s+"azurerm"', re.IGNORECASE),
    "S3": re.compile(r'backend\s+"s3"', re.IGNORECASE),
    "GCS": re.compile(r'backend\s+"gcs"', re.IGNORECASE),
    "Terraform Cloud": re.compile(
        r'backend\s+"remote"|cloud\s*\{', re.IGNORECASE
    ),
}


def _detect_state_backend(workspace: Path) -> Optional[str]:
    """Detect Terraform state backend from ``backend`` blocks in .tf files.

    Heuristics:
    - Scan .tf files for ``backend "azurerm"``, ``backend "s3"``, ``backend "gcs"``
    - Also check for ``cloud {}`` block (Terraform Cloud / HCP)
    - Skip ``.terraform/`` directories
    """
    for tf_file in workspace.rglob("*.tf"):
        if ".terraform" in tf_file.parts:
            continue
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for backend_name, pattern in _BACKEND_PATTERNS.items():
            if pattern.search(content):
                return backend_name
    return None


# Common naming expressions seen in Terraform locals blocks
_NAMING_PATTERNS = [
    # ${var.prefix}-<abbreviation>-<suffix> pattern
    re.compile(
        r'name\s*=\s*"?\$\{var\.prefix\}'
        r'[-_]'
        r'.*'
        r'[-_]'
        r'.*"?',
    ),
    # format() based naming
    re.compile(
        r'name\s*=\s*format\s*\(\s*"[^"]*%s[^"]*%s',
    ),
]


def _detect_naming_pattern(workspace: Path) -> Optional[str]:
    """Infer naming convention from ``locals`` blocks in .tf files.

    Heuristics:
    - Look for ``name = "${var.prefix}-...-..."`` patterns in locals blocks
    - Look for ``format("%s-...", ...)`` naming expressions
    - Extracts the general shape, not exact expressions
    """
    for tf_file in workspace.rglob("*.tf"):
        if ".terraform" in tf_file.parts:
            continue
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Look for locals { ... name = "..." ... }
        for pattern in _NAMING_PATTERNS:
            if pattern.search(content):
                return "{prefix}-{resource_type}-{suffix}"
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_workspace(workspace_path: Path) -> DiscoveryResult:
    """Scan *workspace_path* and return a :class:`DiscoveryResult`.

    Detection summary (see individual ``_detect_*`` functions for details):

    ============== ========================================================
    Field          Heuristic
    ============== ========================================================
    cloud_provider ``provider "azurerm"`` / ``"aws"`` / ``"google"`` blocks
    module_prefix  Directory names matching ``tf-module-*``, etc.
    org_name       Git remote URL (``github.com/ORG/REPO``)
    orchestration  ``terragrunt.hcl`` / ``terramate.tm.hcl`` / ``Pulumi.yaml``
    ci_cd_platform ``.github/workflows/`` / ``azure-pipelines*.yml`` / etc.
    state_backend  ``backend "azurerm"`` / ``"s3"`` / ``"gcs"`` / ``cloud {}``
    naming_pattern ``name = "${var.prefix}-..."`` expressions in locals
    ============== ========================================================
    """
    result = DiscoveryResult(workspace_path=workspace_path)

    result.cloud_provider = _detect_cloud_provider(workspace_path)
    result.module_prefix = _detect_module_prefix(workspace_path)
    result.org_name = _detect_org_from_git(workspace_path)
    result.orchestration_tool, result.orchestration_dir = _detect_orchestration(
        workspace_path
    )
    result.ci_cd_platform, result.pipeline_dir = _detect_ci_cd(workspace_path)
    result.state_backend = _detect_state_backend(workspace_path)
    result.naming_pattern = _detect_naming_pattern(workspace_path)

    result.has_copilot_instructions = (
        workspace_path / ".github" / "copilot-instructions.md"
    ).exists()
    result.has_claude_md = (workspace_path / "CLAUDE.md").exists()

    if result.has_copilot_instructions:
        result.notes.append("Existing .github/copilot-instructions.md detected.")
    if result.has_claude_md:
        result.notes.append("Existing CLAUDE.md detected.")

    return result
