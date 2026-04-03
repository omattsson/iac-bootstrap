"""Workspace auto-detection: scan an IaC workspace to infer defaults."""

from __future__ import annotations

import os
import re
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
    orchestration_tool: Optional[str] = None  # "Terragrunt" | "Terramate" | "None"

    # Directory that holds orchestration config files
    orchestration_dir: Optional[str] = None

    # CI/CD platform inferred from pipeline file locations
    ci_cd_platform: Optional[str] = None

    # Directory where pipeline files live
    pipeline_dir: Optional[str] = None

    # Naming pattern inferred from resource name expressions in .tf files
    naming_pattern: Optional[str] = None

    # State backend type detected from backend blocks in .tf files
    state_backend: Optional[str] = None

    # Auth pattern detected from pipeline configs or provider blocks
    auth_pattern: Optional[str] = None

    # Tag/label strategy detected from merge expressions in .tf files
    tag_strategy: Optional[str] = None

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
        from collections import Counter

        return Counter(candidates).most_common(1)[0][0]
    # Check for a generic "modules/" directory
    if (workspace / "modules").is_dir():
        return "modules"
    return None


def _detect_orchestration(workspace: Path) -> tuple[Optional[str], Optional[str]]:
    """Return (tool_name, dir_name) or (None, None)."""
    for hcl_file in workspace.rglob("terragrunt.hcl"):
        rel = hcl_file.parent.relative_to(workspace)
        parts = rel.parts
        # The orchestration dir is typically the top-level dir containing .hcl files
        orch_dir = parts[0] if parts else "."
        return "Terragrunt", orch_dir
    for hcl_file in workspace.rglob("terramate.tm.hcl"):
        rel = hcl_file.parent.relative_to(workspace)
        parts = rel.parts
        orch_dir = parts[0] if parts else "."
        return "Terramate", orch_dir
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
    """Try to extract organisation name from git remote URL."""
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


def _detect_state_backend(workspace: Path) -> Optional[str]:
    """Detect state backend from Terraform backend blocks in .tf files."""
    backend_pattern = re.compile(
        r'backend\s+"([^"]+)"', re.IGNORECASE
    )
    _BACKEND_MAP = {
        "azurerm": "Azure Blob Storage",
        "s3": "S3",
        "gcs": "GCS",
        "remote": "Terraform Cloud",
        "consul": "Consul",
        "http": "HTTP",
        "pg": "PostgreSQL",
    }
    for tf_file in workspace.rglob("*.tf"):
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = backend_pattern.search(content)
        if m:
            backend_type = m.group(1).lower()
            return _BACKEND_MAP.get(backend_type, backend_type)
    return None


def _detect_naming_pattern(workspace: Path) -> Optional[str]:
    """Infer resource naming pattern from local name expressions in .tf files.

    Scans for ``name = "..."`` expressions that reference ``var.prefix`` or
    ``local.`` and attempts to generalise them into a pattern like
    ``{prefix}-{resource_abbreviation}-{suffix}``.
    """
    name_expr = re.compile(
        r'name\s*=\s*"(\$\{[^}]+\}[^"]*)"', re.IGNORECASE
    )
    candidates: list[str] = []
    for tf_file in workspace.rglob("*.tf"):
        # Skip test files and example files
        rel = str(tf_file.relative_to(workspace))
        if "test" in rel.lower() or "example" in rel.lower():
            continue
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in name_expr.finditer(content):
            expr = m.group(1)
            if "var.prefix" in expr or "local.prefix" in expr:
                candidates.append(expr)

    if not candidates:
        return None

    # Generalise the most common pattern
    from collections import Counter

    most_common = Counter(candidates).most_common(1)[0][0]

    # Convert interpolation expressions to readable pattern tokens
    pattern = most_common
    pattern = re.sub(
        r"\$\{var\.prefix\}|\$\{local\.prefix\}",
        "{prefix}",
        pattern,
    )
    pattern = re.sub(
        r"\$\{local\.resource_abbreviation\}|\$\{local\.abbreviation\}",
        "{resource_abbreviation}",
        pattern,
    )
    pattern = re.sub(
        r"\$\{local\.suffix\}|\$\{var\.suffix\}",
        "{suffix}",
        pattern,
    )
    pattern = re.sub(
        r"\$\{var\.name\}|\$\{local\.name\}",
        "{name}",
        pattern,
    )
    pattern = re.sub(
        r"\$\{local\.\w+\}",
        "{component}",
        pattern,
    )
    pattern = re.sub(
        r"\$\{var\.\w+\}",
        "{var}",
        pattern,
    )
    return pattern


def _detect_auth_pattern(workspace: Path) -> Optional[str]:
    """Detect authentication pattern from pipeline files and provider config.

    Checks for OIDC, Managed Identity, Workload Identity Federation, and
    service principal patterns in CI/CD config and Terraform provider blocks.
    """
    # Check GitHub Actions workflow files
    gh_workflows = workspace / ".github" / "workflows"
    if gh_workflows.is_dir():
        for yml_file in gh_workflows.rglob("*.yml"):
            try:
                content = yml_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "id-token: write" in content:
                if "aws-actions/configure-aws-credentials" in content:
                    return "IAM Roles via OIDC"
                if "azure/login" in content:
                    return "Managed Identity / OIDC"
                if "google-github-actions/auth" in content:
                    return "Workload Identity Federation"
                return "OIDC"

    # Check Azure DevOps pipelines
    for pattern in ("azure-pipelines.yml", "**/azure-pipelines*.yml"):
        for yml_file in workspace.glob(pattern):
            try:
                content = yml_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "azureSubscription" in content or "serviceConnection" in content:
                return "Managed Identity / OIDC"

    # Check GitLab CI
    gitlab_ci = workspace / ".gitlab-ci.yml"
    if gitlab_ci.exists():
        try:
            content = gitlab_ci.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            content = ""
        if "id_tokens:" in content:
            return "OIDC"

    # Fall back to scanning provider blocks
    use_oidc = re.compile(r"use_oidc\s*=\s*true", re.IGNORECASE)
    use_msi = re.compile(r"use_msi\s*=\s*true", re.IGNORECASE)
    for tf_file in workspace.rglob("*.tf"):
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if use_oidc.search(content):
            return "Managed Identity / OIDC"
        if use_msi.search(content):
            return "Managed Identity / OIDC"
    return None


def _detect_tag_strategy(workspace: Path) -> Optional[str]:
    """Detect tag/label merge strategy from .tf files.

    Looks for ``merge(var.env_default_tags, var.tags)`` or similar patterns.
    """
    merge_pattern = re.compile(
        r"merge\(\s*var\.(\w+)\s*,\s*var\.(\w+)\s*\)", re.IGNORECASE
    )
    for tf_file in workspace.rglob("*.tf"):
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = merge_pattern.search(content)
        if m:
            return f"merge(var.{m.group(1)}, var.{m.group(2)})"
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_workspace(workspace_path: Path) -> DiscoveryResult:
    """Scan *workspace_path* and return a :class:`DiscoveryResult`."""
    result = DiscoveryResult(workspace_path=workspace_path)

    result.cloud_provider = _detect_cloud_provider(workspace_path)
    result.module_prefix = _detect_module_prefix(workspace_path)
    result.org_name = _detect_org_from_git(workspace_path)
    result.orchestration_tool, result.orchestration_dir = _detect_orchestration(
        workspace_path
    )
    result.ci_cd_platform, result.pipeline_dir = _detect_ci_cd(workspace_path)
    result.naming_pattern = _detect_naming_pattern(workspace_path)
    result.state_backend = _detect_state_backend(workspace_path)
    result.auth_pattern = _detect_auth_pattern(workspace_path)
    result.tag_strategy = _detect_tag_strategy(workspace_path)

    result.has_copilot_instructions = (
        workspace_path / ".github" / "copilot-instructions.md"
    ).exists()
    result.has_claude_md = (workspace_path / "CLAUDE.md").exists()

    if result.has_copilot_instructions:
        result.notes.append("Existing .github/copilot-instructions.md detected.")
    if result.has_claude_md:
        result.notes.append("Existing CLAUDE.md detected.")

    return result
