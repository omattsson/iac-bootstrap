"""Workspace auto-detection: scan an IaC workspace to infer defaults."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


# Directories never worth scanning. Pruned during the walk, both for speed on
# large repositories and to avoid false positives from vendored/cache content.
DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".terraform",
        ".terragrunt-cache",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".idea",
        ".vscode",
    }
)

# Canonical cloud order — used to break ties for the primary provider so the
# choice is stable and matches the historical (dict-insertion) behaviour.
_CLOUD_ORDER = ["Azure", "AWS", "GCP"]


@dataclass
class Signal:
    """A single piece of evidence for an inferred value.

    ``source`` names the file or signal the value was traced to, so every
    inferred value can be explained.
    """

    field: str  # the DiscoveryResult field this supports, e.g. "cloud_provider"
    value: str | bool  # the inferred value, e.g. "Azure" or True for a flag
    source: str  # workspace-relative file path or signal, e.g. "main.tf"
    detail: str = ""  # the matched token/expression, e.g. 'provider "azurerm"'

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "value": self.value,
            "source": self.source,
            "detail": self.detail,
        }


@dataclass
class DiscoveryResult:
    """Results of a workspace scan used to seed interview defaults."""

    workspace_path: Path

    # Primary cloud provider (the one with the most signals) — kept for
    # backward compatibility with single-cloud callers.
    cloud_provider: Optional[str] = None  # "Azure" | "AWS" | "GCP"

    # All cloud providers detected, ordered by signal count (descending).
    cloud_providers: list[str] = field(default_factory=list)

    # Module directory prefix (e.g. "tf-module", "terraform-aws")
    module_prefix: Optional[str] = None

    # Organisation name guessed from git remote URL
    org_name: Optional[str] = None

    # Orchestration tool detected from config files
    orchestration_tool: Optional[str] = None  # "Terragrunt" | "Terramate" | "Pulumi" | None when not detected

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

    # Evidence backing each inferred value.
    signals: list[Signal] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of the result."""
        return {
            "workspace_path": str(self.workspace_path),
            "cloud_provider": self.cloud_provider,
            "cloud_providers": list(self.cloud_providers),
            "module_prefix": self.module_prefix,
            "org_name": self.org_name,
            "orchestration_tool": self.orchestration_tool,
            "orchestration_dir": self.orchestration_dir,
            "ci_cd_platform": self.ci_cd_platform,
            "pipeline_dir": self.pipeline_dir,
            "state_backend": self.state_backend,
            "naming_pattern": self.naming_pattern,
            "has_copilot_instructions": self.has_copilot_instructions,
            "has_claude_md": self.has_claude_md,
            "notes": list(self.notes),
            "signals": [s.to_dict() for s in self.signals],
        }


# ---------------------------------------------------------------------------
# File walking
# ---------------------------------------------------------------------------


def _iter_files(
    workspace: Path,
    ignored: frozenset[str],
    match: Optional[Callable[[str], bool]] = None,
) -> list[Path]:
    """Return files under *workspace*, pruning *ignored* directories.

    Uses :func:`os.walk` and removes ignored directories in-place so the walk
    never descends into them — this keeps scanning safe on large repositories
    (for example ones with a big ``node_modules``). The result is sorted for
    deterministic detection.
    """
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(workspace):
        dirnames[:] = [d for d in dirnames if d not in ignored]
        for name in filenames:
            if match is None or match(name):
                results.append(Path(dirpath) / name)
    results.sort()
    return results


def _rel(path: Path, workspace: Path) -> str:
    """Workspace-relative POSIX path for use in evidence."""
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)


def _strip_block_comments(content: str) -> str:
    """Remove ``/* ... */`` block comments from HCL content."""
    return _BLOCK_COMMENT_RE.sub('', content)


# Cloud provider -> the Terraform provider name used in HCL.
_PROVIDER_NAMES = {"Azure": "azurerm", "AWS": "aws", "GCP": "google"}

_PROVIDER_PATTERNS = {
    "Azure": re.compile(
        r'^(?!\s*(?:#|//))\s*provider\s+"azurerm"',
        re.IGNORECASE | re.MULTILINE,
    ),
    "AWS": re.compile(
        r'^(?!\s*(?:#|//))\s*provider\s+"aws"',
        re.IGNORECASE | re.MULTILINE,
    ),
    "GCP": re.compile(
        r'^(?!\s*(?:#|//))\s*provider\s+"google"',
        re.IGNORECASE | re.MULTILINE,
    ),
}

_PROVIDER_REQUIRED_PATTERNS = {
    "Azure": re.compile(
        r'^(?!\s*(?:#|//))\s*source\s*=\s*"hashicorp/azurerm"',
        re.IGNORECASE | re.MULTILINE,
    ),
    "AWS": re.compile(
        r'^(?!\s*(?:#|//))\s*source\s*=\s*"hashicorp/aws"',
        re.IGNORECASE | re.MULTILINE,
    ),
    "GCP": re.compile(
        r'^(?!\s*(?:#|//))\s*source\s*=\s*"hashicorp/google"',
        re.IGNORECASE | re.MULTILINE,
    ),
}


def _detect_cloud_provider(
    workspace: Path, *, ignored: frozenset[str] = DEFAULT_IGNORED_DIRS
) -> Optional[str]:
    """Return the primary detected cloud provider, or ``None``."""
    tf = _scan_tf_files(workspace, ignored)
    if not any(tf.cloud_counts.values()):
        return None
    return _primary_cloud(tf.cloud_counts)


def _primary_cloud(counts: dict[str, int]) -> Optional[str]:
    ordered = _clouds_by_count(counts)
    return ordered[0] if ordered else None


def _clouds_by_count(counts: dict[str, int]) -> list[str]:
    """Providers with at least one signal, ordered by count then canonical order.

    Ties are broken by :data:`_CLOUD_ORDER` (Azure, AWS, GCP), preserving the
    historical primary-provider choice.
    """
    def _order_index(provider: str) -> int:
        return _CLOUD_ORDER.index(provider) if provider in _CLOUD_ORDER else len(_CLOUD_ORDER)

    return [
        provider
        for provider in sorted(counts, key=lambda k: (-counts[k], _order_index(k)))
        if counts[provider] > 0
    ]


def _detect_module_prefix(workspace: Path) -> Optional[str]:
    """Guess module prefix from directory names like tf-module-*, modules/."""
    prefix, _source = _detect_module_prefix_detailed(workspace)
    return prefix


def _detect_module_prefix_detailed(
    workspace: Path,
) -> tuple[Optional[str], Optional[str]]:
    """Return (prefix, example directory) or (None, None)."""
    candidates: list[tuple[str, str]] = []
    try:
        entries = sorted(workspace.iterdir(), key=lambda e: e.name)
    except OSError:
        entries = []
    for entry in entries:
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
                candidates.append((m.group(1), name))
                break
    if candidates:
        prefixes = Counter(prefix for prefix, _ in candidates)
        winner = prefixes.most_common(1)[0][0]
        example = next(name for prefix, name in candidates if prefix == winner)
        return winner, example
    if (workspace / "modules").is_dir():
        return "modules", "modules/"
    return None, None


_ORCH_MARKERS = [
    ("Terragrunt", "terragrunt.hcl"),
    ("Terramate", "terramate.tm.hcl"),
    ("Pulumi", "Pulumi.yaml"),
]


def _detect_orchestration(
    workspace: Path, *, ignored: frozenset[str] = DEFAULT_IGNORED_DIRS
) -> tuple[Optional[str], Optional[str]]:
    """Return (tool_name, dir_name) or (None, None)."""
    tool, orch_dir, _source = _detect_orchestration_detailed(workspace, ignored)
    return tool, orch_dir


def _detect_orchestration_detailed(
    workspace: Path, ignored: frozenset[str]
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (tool_name, dir_name, source_file) or (None, None, None).

    Terragrunt takes priority, then Terramate, then Pulumi.
    """
    markers = {marker for _tool, marker in _ORCH_MARKERS}
    found: dict[str, list[Path]] = {}
    for path in _iter_files(workspace, ignored, lambda n: n in markers):
        found.setdefault(path.name, []).append(path)
    for tool, marker in _ORCH_MARKERS:
        if found.get(marker):
            marker_file = sorted(found[marker])[0]
            rel = marker_file.parent.relative_to(workspace)
            orch_dir = rel.parts[0] if rel.parts else "."
            return tool, orch_dir, _rel(marker_file, workspace)
    return None, None, None


_PIPELINE_SUFFIXES = (".yml", ".yaml")


def _detect_ci_cd(
    workspace: Path, *, ignored: frozenset[str] = DEFAULT_IGNORED_DIRS
) -> tuple[Optional[str], Optional[str]]:
    """Return (platform_name, pipeline_dir) or (None, None)."""
    platform, pipeline_dir, _source = _detect_ci_cd_detailed(workspace, ignored)
    return platform, pipeline_dir


def _detect_ci_cd_detailed(
    workspace: Path, ignored: frozenset[str]
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (platform, pipeline_dir, source_file) or (None, None, None)."""
    # GitHub Actions — only when the workflows directory actually contains a
    # workflow file. An empty .github/workflows/ is not a signal.
    wf_dir = workspace / ".github" / "workflows"
    if wf_dir.is_dir():
        wf_files = sorted(
            f
            for f in wf_dir.rglob("*")
            if f.is_file() and f.suffix in _PIPELINE_SUFFIXES
        )
        if wf_files:
            return "GitHub Actions", ".github/workflows", _rel(wf_files[0], workspace)

    # Azure DevOps — a root azure-pipelines.yml/.yaml, else one anywhere.
    for name in ("azure-pipelines.yml", "azure-pipelines.yaml"):
        root_pipeline = workspace / name
        if root_pipeline.is_file():
            return "Azure DevOps", ".", name
    azure = _iter_files(
        workspace,
        ignored,
        lambda n: n.startswith("azure-pipelines") and n.endswith(_PIPELINE_SUFFIXES),
    )
    if azure:
        return (
            "Azure DevOps",
            _rel(azure[0].parent, workspace),
            _rel(azure[0], workspace),
        )

    # GitLab CI
    for name in (".gitlab-ci.yml", ".gitlab-ci.yaml"):
        gitlab = workspace / name
        if gitlab.is_file():
            return "GitLab CI", ".", name

    # A generic pipelines/ directory of YAML files. The `pipelines` segment must
    # be within the workspace, not somewhere in the checkout's absolute path.
    pipeline_files = [
        f
        for f in _iter_files(workspace, ignored, lambda n: n.endswith(_PIPELINE_SUFFIXES))
        if "pipelines" in f.relative_to(workspace).parts
    ]
    if pipeline_files:
        return (
            "Unknown",
            _rel(pipeline_files[0].parent, workspace),
            _rel(pipeline_files[0], workspace),
        )

    return None, None, None


def _detect_org_from_git(workspace: Path) -> Optional[str]:
    """Try to extract organisation name from a git remote URL."""
    org, _source = _detect_org_from_git_detailed(workspace)
    return org


def _detect_org_from_git_detailed(
    workspace: Path,
) -> tuple[Optional[str], Optional[str]]:
    """Return (org, source) or (None, None).

    Heuristic: parse ``.git/config`` for a remote URL and extract the
    organisation segment from ``github.com/ORG/REPO`` or ``git@...:ORG/REPO``.
    Walks up parent directories to find a git root if needed.
    """
    git_config = workspace / ".git" / "config"
    if not git_config.exists():
        for parent in workspace.parents:
            if (parent / ".git" / "config").exists():
                git_config = parent / ".git" / "config"
                break
        else:
            return None, None
    try:
        content = git_config.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, None
    m = re.search(r"url\s*=\s*.*[:/]([^/\s]+)/[^/\s]+(?:\.git)?", content)
    if m:
        # Only report a workspace-relative source; a git root above the
        # workspace is reported as a plain signal, not an absolute path.
        try:
            source = f"git remote ({git_config.relative_to(workspace).as_posix()})"
        except ValueError:
            source = "git remote"
        return m.group(1), source
    return None, None


# ---------------------------------------------------------------------------
# State backend & naming pattern detection
# ---------------------------------------------------------------------------

_BACKEND_PATTERNS = {
    "Azure Blob Storage": re.compile(
        r'^(?!\s*(?:#|//))\s*backend\s+"azurerm"',
        re.IGNORECASE | re.MULTILINE,
    ),
    "S3": re.compile(
        r'^(?!\s*(?:#|//))\s*backend\s+"s3"',
        re.IGNORECASE | re.MULTILINE,
    ),
    "GCS": re.compile(
        r'^(?!\s*(?:#|//))\s*backend\s+"gcs"',
        re.IGNORECASE | re.MULTILINE,
    ),
    "Terraform Cloud / Enterprise": re.compile(
        r'^(?!\s*(?:#|//))\s*(?:backend\s+"remote"|cloud\s*\{)',
        re.IGNORECASE | re.MULTILINE,
    ),
}


def _detect_state_backend(
    workspace: Path, *, ignored: frozenset[str] = DEFAULT_IGNORED_DIRS
) -> Optional[str]:
    """Detect Terraform state backend using the shared .tf file scanner."""
    return _scan_tf_files(workspace, ignored).state_backend


def _match_state_backend(content: str) -> Optional[str]:
    """Return matching backend name from *content*, or ``None``."""
    for backend_name, pattern in _BACKEND_PATTERNS.items():
        if pattern.search(content):
            return backend_name
    return None


# Common naming expressions seen in Terraform .tf files
_NAMING_PATTERNS = [
    # ${var.prefix}-<abbreviation>-<suffix> pattern
    re.compile(
        r'^(?!\s*(?:#|//))'
        r'.*name\s*=\s*"?\$\{var\.prefix\}'
        r'[-_]'
        r'.*'
        r'[-_]'
        r'.*"?',
        re.MULTILINE,
    ),
    # format() based naming
    re.compile(
        r'^(?!\s*(?:#|//))'
        r'.*name\s*=\s*format\s*\(\s*"[^"]*%s[^"]*%s',
        re.MULTILINE,
    ),
]


def _detect_naming_pattern(
    workspace: Path, *, ignored: frozenset[str] = DEFAULT_IGNORED_DIRS
) -> Optional[str]:
    """Infer naming convention using the shared .tf file scanner."""
    return _scan_tf_files(workspace, ignored).naming_pattern


def _match_naming_pattern(content: str) -> bool:
    """Return ``True`` if *content* contains a recognisable naming pattern."""
    for pattern in _NAMING_PATTERNS:
        if pattern.search(content):
            return True
    return False


@dataclass
class _TfScanResult:
    """Aggregated results from a single pass over all .tf files."""

    cloud_counts: dict[str, int] = field(
        default_factory=lambda: {"Azure": 0, "AWS": 0, "GCP": 0}
    )
    signals: list[Signal] = field(default_factory=list)
    state_backend: Optional[str] = None
    state_backend_source: Optional[str] = None
    naming_pattern: Optional[str] = None
    naming_source: Optional[str] = None


def _scan_tf_files(workspace: Path, ignored: frozenset[str]) -> _TfScanResult:
    """Read every .tf file once and run all detection regexes in one pass."""
    result = _TfScanResult()
    for tf_file in _iter_files(workspace, ignored, lambda n: n.endswith(".tf")):
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        content = _strip_block_comments(content)
        rel = _rel(tf_file, workspace)

        # Count each provider at most once per file, so a provider that appears
        # in both a ``provider`` block and ``required_providers`` in the same
        # file does not outweigh one used across more files. The signal records
        # whichever form was found (the provider block takes precedence).
        for provider in _PROVIDER_NAMES:
            if _PROVIDER_PATTERNS[provider].search(content):
                detail = f'provider "{_PROVIDER_NAMES[provider]}"'
            elif _PROVIDER_REQUIRED_PATTERNS[provider].search(content):
                detail = (
                    f'required_providers source "hashicorp/{_PROVIDER_NAMES[provider]}"'
                )
            else:
                continue
            result.cloud_counts[provider] += 1
            result.signals.append(Signal("cloud_provider", provider, rel, detail))

        if result.state_backend is None:
            backend = _match_state_backend(content)
            if backend:
                result.state_backend = backend
                result.state_backend_source = rel
        if result.naming_pattern is None and _match_naming_pattern(content):
            result.naming_pattern = "{prefix}-{resource_abbreviation}-{suffix}"
            result.naming_source = rel
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_workspace(
    workspace_path: Path, *, ignored_dirs: Optional[list[str]] = None
) -> DiscoveryResult:
    """Scan *workspace_path* and return a :class:`DiscoveryResult`.

    Parameters
    ----------
    workspace_path:
        The IaC workspace to scan.
    ignored_dirs:
        Extra directory names to skip, merged with
        :data:`DEFAULT_IGNORED_DIRS`.

    Detection summary (see individual ``_detect_*`` functions for details):

    ============== ========================================================
    Field          Heuristic
    ============== ========================================================
    cloud_provider ``provider "azurerm"`` / ``"aws"`` / ``"google"`` blocks;
                   ``required_providers`` with ``source = "hashicorp/..."``.
                   All detected providers are reported in ``cloud_providers``.
    module_prefix  Directory names matching ``tf-module-*``, etc.
    org_name       Git remote URL (``github.com/ORG/REPO``)
    orchestration  ``terragrunt.hcl`` / ``terramate.tm.hcl`` / ``Pulumi.yaml``
    ci_cd_platform ``.github/workflows/`` with a workflow file /
                   ``azure-pipelines*.yml|yaml`` / ``.gitlab-ci.yml|yaml``
    state_backend  ``backend "azurerm"`` / ``"s3"`` / ``"gcs"`` / ``cloud {}`` /
                   ``backend "remote"``
    naming_pattern ``name = "${var.prefix}-..."`` or ``format(...)`` naming
                   expressions in .tf files
    ============== ========================================================

    Each value that discovery populates is backed by a :class:`Signal` in
    ``signals`` naming the file or signal it came from. A field that is not
    detected has no signal.
    """
    ignored = DEFAULT_IGNORED_DIRS
    if ignored_dirs:
        # frozenset.union returns a frozenset, so the ignore list stays immutable.
        ignored = DEFAULT_IGNORED_DIRS.union(ignored_dirs)

    result = DiscoveryResult(workspace_path=workspace_path)

    # Single-pass scan of all .tf files for cloud, backend, and naming.
    tf = _scan_tf_files(workspace_path, ignored)
    result.cloud_providers = _clouds_by_count(tf.cloud_counts)
    result.cloud_provider = result.cloud_providers[0] if result.cloud_providers else None
    result.signals.extend(tf.signals)

    result.state_backend = tf.state_backend
    if tf.state_backend and tf.state_backend_source:
        result.signals.append(
            Signal("state_backend", tf.state_backend, tf.state_backend_source, "backend block")
        )
    result.naming_pattern = tf.naming_pattern
    if tf.naming_pattern and tf.naming_source:
        result.signals.append(
            Signal("naming_pattern", tf.naming_pattern, tf.naming_source, "name expression")
        )

    prefix, prefix_source = _detect_module_prefix_detailed(workspace_path)
    result.module_prefix = prefix
    if prefix and prefix_source:
        result.signals.append(Signal("module_prefix", prefix, prefix_source))

    org, org_source = _detect_org_from_git_detailed(workspace_path)
    result.org_name = org
    if org:
        result.signals.append(Signal("org_name", org, org_source or "git remote"))

    tool, orch_dir, orch_source = _detect_orchestration_detailed(workspace_path, ignored)
    result.orchestration_tool = tool
    result.orchestration_dir = orch_dir
    if tool and orch_source:
        result.signals.append(Signal("orchestration_tool", tool, orch_source))
        if orch_dir:
            result.signals.append(Signal("orchestration_dir", orch_dir, orch_source))

    platform, pipeline_dir, ci_source = _detect_ci_cd_detailed(workspace_path, ignored)
    result.ci_cd_platform = platform
    result.pipeline_dir = pipeline_dir
    if platform and ci_source:
        result.signals.append(Signal("ci_cd_platform", platform, ci_source))
        if pipeline_dir:
            result.signals.append(Signal("pipeline_dir", pipeline_dir, ci_source))

    result.has_copilot_instructions = (
        workspace_path / ".github" / "copilot-instructions.md"
    ).exists()
    result.has_claude_md = (workspace_path / "CLAUDE.md").exists()
    if result.has_copilot_instructions:
        result.signals.append(
            Signal(
                "has_copilot_instructions",
                True,
                ".github/copilot-instructions.md",
            )
        )
    if result.has_claude_md:
        result.signals.append(Signal("has_claude_md", True, "CLAUDE.md"))

    if len(result.cloud_providers) > 1:
        result.notes.append(
            "Multiple cloud providers detected: "
            + ", ".join(result.cloud_providers)
            + f". Using {result.cloud_provider} (most signals)."
        )
    if result.has_copilot_instructions:
        result.notes.append("Existing .github/copilot-instructions.md detected.")
    if result.has_claude_md:
        result.notes.append("Existing CLAUDE.md detected.")

    return result
