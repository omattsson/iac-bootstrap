"""Standalone IaC maturity assessment (issue #54).

Scores a workspace against the ten practice areas in
``references/maturity-report.md.tmpl`` using discovery plus a set of read-only
filesystem probes. No interview, and nothing is generated into the workspace.

The scoring model is the template's own:

* Adopted = full category weight, Partial = half, Missing = zero.
* A category that does not apply is marked N/A and excluded, and the remaining
  weights are renormalised to 100.
* Critical gap = any Missing category, or a Partial in a category weighted 15
  or more (Testing, CI/CD, Security, Module Design).
* Moderate gap = a Partial in a lighter category.

Every category records the evidence it scored from, so a result can be traced
back to the files that produced it rather than taken on trust.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from bootstrap_iac.discovery import (
    DEFAULT_IGNORED_DIRS,
    DiscoveryResult,
    _strip_block_comments,
)

# --- Status vocabulary -------------------------------------------------------

ADOPTED = "adopted"
PARTIAL = "partial"
MISSING = "missing"
NOT_APPLICABLE = "na"

_STATUS_SYMBOL = {
    ADOPTED: "✅ Adopted",
    PARTIAL: "⚠️ Partial",
    MISSING: "❌ Missing",
    NOT_APPLICABLE: "— N/A",
}
_STATUS_FACTOR = {ADOPTED: 1.0, PARTIAL: 0.5, MISSING: 0.0}

# Categories and weights, in the order the report table presents them.
CATEGORIES: tuple[tuple[str, str, int], ...] = (
    ("module_design", "Module Design", 15),
    ("naming", "Naming & Tagging", 10),
    ("variable", "Variable Design", 5),
    ("testing", "Testing", 15),
    ("orchestration", "Orchestration", 5),
    ("cicd", "CI/CD", 15),
    ("security", "Security", 20),
    ("code_quality", "Code Quality", 5),
    ("state", "State Management", 5),
    ("rollout", "Progressive Rollout", 5),
)

# A Partial here is still critical: these areas carry the most risk.
_HIGH_WEIGHT = 15

# Remediation hint per category, used for the recommended actions list.
_ACTIONS = {
    "module_design": "Split each module into main.tf, variables.tf and outputs.tf.",
    "naming": "Adopt one naming pattern in locals.tf and merge default tags on every resource.",
    "variable": "Give every variable a description and a type, and use optional() for object attributes.",
    "testing": "Add native `.tftest.hcl` plan tests for each module's naming, tagging and conditionals.",
    "orchestration": "Move shared values into the orchestration layer's common config rather than per environment.",
    "cicd": "Add a plan-on-change, approve-then-apply pipeline with identity-based authentication.",
    "security": "Add policy scanning (checkov, tflint or OPA) to the pipeline and keep secrets out of the repository.",
    "code_quality": "Enforce `terraform fmt` and a linter, ideally through pre-commit and CI.",
    "state": "Use a remote state backend with locking, configured per environment.",
    "rollout": "Promote changes through separate environments rather than applying everywhere at once.",
}

_RATINGS = (
    (80, "🟢 Strong"),
    (60, "🟡 Developing"),
    (40, "🟠 Foundational"),
    (0, "🔴 Early"),
)


@dataclass
class CategoryScore:
    """One practice area's result, with the evidence it was scored from."""

    key: str
    title: str
    weight: int
    status: str
    evidence: list[str] = field(default_factory=list)

    @property
    def points(self) -> float:
        if self.status == NOT_APPLICABLE:
            return 0.0
        return self.weight * _STATUS_FACTOR[self.status]

    @property
    def symbol(self) -> str:
        return _STATUS_SYMBOL[self.status]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "weight": self.weight,
            "status": self.status,
            "points": round(self.points, 2),
            "evidence": self.evidence,
        }


@dataclass
class MaturityReport:
    """The assessed workspace: category scores, overall score and gaps."""

    workspace: Path
    categories: list[CategoryScore]
    company: str = "this workspace"

    # -- derived values ----------------------------------------------------

    @property
    def applicable(self) -> list[CategoryScore]:
        return [c for c in self.categories if c.status != NOT_APPLICABLE]

    @property
    def earned_points(self) -> float:
        return sum(c.points for c in self.applicable)

    @property
    def available_points(self) -> int:
        return sum(c.weight for c in self.applicable)

    @property
    def score_exact(self) -> float:
        """Unrounded percentage, with N/A categories excluded.

        Points are multiples of 0.5, so a score of 79.5 is reachable. Gating
        compares against this, and only display rounds (issue #54 review).
        """
        if not self.available_points:
            return 0.0
        return self.earned_points / self.available_points * 100

    @property
    def overall_score(self) -> float:
        """The one score used for display, rating and gating.

        Rounded to one decimal place, and that same number is what the report
        prints, what the rating band is chosen from, and what the threshold is
        compared against. Rounding to an integer for display while rating and
        gating on the exact value made a 79.5 print as "80%" yet rate
        Developing and fail a threshold of 80 (issue #54 review).
        """
        return round(self.score_exact, 1)

    @property
    def display_score(self) -> str:
        """The canonical score as printed: "80" or "79.5", never "80.0"."""
        return _fmt_points(self.overall_score)

    @property
    def rating(self) -> str:
        for floor, label in _RATINGS:
            if self.overall_score >= floor:
                return label
        return _RATINGS[-1][1]  # pragma: no cover - the 0 floor always matches

    @property
    def critical_gaps(self) -> list[CategoryScore]:
        return [
            c
            for c in self.applicable
            if c.status == MISSING
            or (c.status == PARTIAL and c.weight >= _HIGH_WEIGHT)
        ]

    @property
    def moderate_gaps(self) -> list[CategoryScore]:
        return [
            c
            for c in self.applicable
            if c.status == PARTIAL and c.weight < _HIGH_WEIGHT
        ]

    @property
    def strengths(self) -> list[CategoryScore]:
        return [c for c in self.applicable if c.status == ADOPTED]

    # -- output ------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "workspace": str(self.workspace),
            "company": self.company,
            "assessed": date.today().isoformat(),
            "overall_score": self.overall_score,
            "score_exact": round(self.score_exact, 2),
            "earned_points": round(self.earned_points, 2),
            "available_points": self.available_points,
            "rating": self.rating,
            "categories": [c.to_dict() for c in self.categories],
            "critical_gaps": [c.key for c in self.critical_gaps],
            "moderate_gaps": [c.key for c in self.moderate_gaps],
            "strengths": [c.key for c in self.strengths],
            "recommended_actions": self.recommended_actions(),
        }

    def to_json(self) -> str:
        # ensure_ascii=False keeps the rating symbols readable in the output.
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def recommended_actions(self) -> list[str]:
        """Remediation hints, most critical and heaviest first."""
        ordered = sorted(
            self.critical_gaps + self.moderate_gaps,
            key=lambda c: (c not in self.critical_gaps, -c.weight, c.title),
        )
        return [f"{c.title}: {_ACTIONS[c.key]}" for c in ordered]

    def context(self, assessor: str = "bootstrap-iac") -> dict:
        """Placeholder values for references/maturity-report.md.tmpl."""
        ctx: dict[str, str] = {
            "COMPANY_NAME": self.company,
            "WORKSPACE_DESCRIPTION": str(self.workspace),
            "ASSESSMENT_DATE": date.today().isoformat(),
            "ASSESSOR": assessor,
            "OVERALL_SCORE": self.display_score,
            # The Total row is out of 100, so it must show the normalised score.
            # Raw earned points read "95/100" beside an overall "100%" whenever
            # a category is N/A (issue #54 review).
            "OVERALL_SCORE_POINTS": self.display_score,
            "MATURITY_RATING": self.rating,
            "CRITICAL_GAP_COUNT": str(len(self.critical_gaps)),
            "MODERATE_GAP_COUNT": str(len(self.moderate_gaps)),
            "STRENGTH_COUNT": str(len(self.strengths)),
            "CRITICAL_GAPS_CONTENT": _gap_list(self.critical_gaps, "No critical gaps found."),
            "MODERATE_GAPS_CONTENT": _gap_list(self.moderate_gaps, "No moderate gaps found."),
            "STRENGTHS_CONTENT": _gap_list(self.strengths, "No established strengths detected yet."),
            "RECOMMENDED_ACTIONS_CONTENT": _numbered(self.recommended_actions()),
        }
        for cat in self.categories:
            prefix = _PLACEHOLDER_PREFIX[cat.key]
            ctx[f"{prefix}_STATUS"] = cat.symbol
            ctx[f"{prefix}_POINTS"] = _fmt_points(cat.points)
        return ctx

    def render(self, templates_dir: Optional[Path] = None, assessor: str = "bootstrap-iac") -> str:
        """Render the Markdown report from the maturity-report template."""
        from bootstrap_iac.generator import get_templates_dir, resolve_placeholders

        root = Path(templates_dir) if templates_dir else get_templates_dir()
        template = root / "maturity-report.md.tmpl"
        text = template.read_text(encoding="utf-8")
        return resolve_placeholders(text, self.context(assessor=assessor))


# Template placeholders use their own prefixes; map them once.
_PLACEHOLDER_PREFIX = {
    "module_design": "MODULE_DESIGN",
    "naming": "NAMING",
    "variable": "VARIABLE",
    "testing": "TESTING",
    "orchestration": "ORCHESTRATION",
    "cicd": "CICD",
    "security": "SECURITY",
    "code_quality": "CODE_QUALITY",
    "state": "STATE",
    "rollout": "ROLLOUT",
}


def _fmt_points(points: float) -> str:
    """Render points without a trailing .0, so 15.0 prints as 15."""
    return str(int(points)) if float(points).is_integer() else f"{points:.1f}"


def _gap_list(items: list[CategoryScore], empty: str) -> str:
    if not items:
        return empty
    lines = []
    for cat in items:
        evidence = f" ({'; '.join(cat.evidence)})" if cat.evidence else ""
        lines.append(f"- **{cat.title}** — {cat.symbol}{evidence}")
    return "\n".join(lines)


def _numbered(items: list[str]) -> str:
    if not items:
        return "No action needed; every assessed category is adopted."
    return "\n".join(f"{i}. {line}" for i, line in enumerate(items, 1))


# --- Probes ------------------------------------------------------------------


def _walk(workspace: Path, ignored: frozenset[str]) -> list[Path]:
    """Regular files under *workspace*, with ignored directories pruned.

    Only regular files are returned: reading a FIFO would block forever, which
    the CLI already guards against elsewhere (issue #54 review).
    """
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(workspace):
        dirnames[:] = [d for d in dirnames if d not in ignored]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                if stat.S_ISREG(os.stat(path, follow_symlinks=False).st_mode):
                    results.append(path)
            except OSError:
                continue
    results.sort()
    return results


def _code(path: Path) -> str:
    """File contents with block comments removed, for HCL pattern matching."""
    return _strip_block_comments(_read(path))


def _search_tf(tf_files: list[Path], pattern: "re.Pattern[str]") -> Optional[tuple[Path, str]]:
    """Return the first (file, match) for *pattern*, scanning every file.

    Scans per file rather than concatenating, so no cap is needed and a match
    late in a large repository is still found (issue #54 review).
    """
    for path in tf_files:
        found = pattern.search(_code(path))
        if found:
            return path, found.group(0)
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _rel(path: Path, workspace: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:  # pragma: no cover - paths always come from the walk
        return path.name


def _score(
    key: str, status: str, evidence: Optional[list[str]] = None
) -> CategoryScore:
    title, weight = next((t, w) for k, t, w in CATEGORIES if k == key)
    return CategoryScore(key, title, weight, status, evidence or [])


def assess(
    discovery: DiscoveryResult,
    workspace: Optional[Path] = None,
    ignored_dirs: Optional[list[str]] = None,
    company: str = "this workspace",
) -> MaturityReport:
    """Assess *workspace* and return its maturity report.

    Read-only: every category is scored from discovery plus filesystem probes,
    and nothing is written.
    """
    ws = Path(workspace or discovery.workspace_path).resolve()
    ignored = DEFAULT_IGNORED_DIRS | frozenset(ignored_dirs or ())
    files = _walk(ws, ignored)

    tf_files = [p for p in files if p.suffix == ".tf"]
    names = {_rel(p, ws) for p in files}
    basenames = {p.name for p in files}
    modules = _module_dirs(tf_files)
    pipelines = _pipeline_files(files, names, ws)
    pipeline_text = "\n".join(_read(p) for p in pipelines).lower()

    scores = [
        _module_design(ws, modules),
        _naming(discovery, tf_files, ws),
        _variable_design(tf_files),
        _testing(files, modules),
        _orchestration(discovery),
        _cicd(discovery, pipelines, pipeline_text, ws),
        _security(files, basenames, _secret_scan_files(files), pipeline_text, ws),
        _code_quality(basenames, pipelines, pipeline_text),
        _state(tf_files, ws),
        _rollout(ws, ignored),
    ]
    return MaturityReport(workspace=ws, categories=scores, company=company)


_MODULE_FILES = ("main.tf", "variables.tf", "outputs.tf")


def _module_dirs(tf_files: list[Path]) -> list[Path]:
    """Directories that hold a reusable module.

    When the workspace has a ``modules/`` tree, only those count: an
    environment or root stack is a caller, not a module, and should not be
    expected to carry outputs.tf or its own tests (issue #54 review).
    """
    dirs = sorted({p.parent for p in tf_files})
    under_modules = [d for d in dirs if "modules" in d.parts]
    return under_modules or dirs


# Adopted needs most modules to follow the split, not just one of them.
_MODULE_ADOPTED_RATIO = 0.8


def _module_design(ws: Path, dirs: list[Path]) -> CategoryScore:
    if not dirs:
        return _score("module_design", MISSING, ["no .tf files found"])
    complete = [
        d
        for d in dirs
        if all((d / f).is_file() for f in _MODULE_FILES)
    ]
    ratio = len(complete) / len(dirs)
    detail = f"{len(complete)}/{len(dirs)} module(s) split into {', '.join(_MODULE_FILES)}"
    if ratio >= _MODULE_ADOPTED_RATIO:
        return _score("module_design", ADOPTED, [detail])
    if complete:
        return _score("module_design", PARTIAL, [f"only {detail}"])
    return _score(
        "module_design",
        PARTIAL,
        [f"{len(dirs)} Terraform directory(ies), none with the full file split"],
    )


_TAG_MERGE = re.compile(r"\bmerge\s*\(\s*(var|local)\.[A-Za-z0-9_]*(tags|labels)", re.I)


def _naming(discovery: DiscoveryResult, tf_files: list[Path], ws: Path) -> CategoryScore:
    evidence = []
    has_naming = bool(discovery.naming_pattern)
    if has_naming:
        evidence.append(f"naming pattern detected: {discovery.naming_pattern}")
    tag_hit = _search_tf(tf_files, _TAG_MERGE)
    has_tags = tag_hit is not None
    if tag_hit:
        evidence.append(f"tag/label merge in {_rel(tag_hit[0], ws)}")
    if has_naming and has_tags:
        return _score("naming", ADOPTED, evidence)
    if has_naming or has_tags:
        return _score("naming", PARTIAL, evidence or ["only one of naming or tagging found"])
    return _score("naming", MISSING, ["no naming pattern or tag merge detected"])


_VARIABLE_OPEN = re.compile(
    r'^(?!\s*(?:#|//))\s*variable\s+"[^"]+"\s*\{', re.MULTILINE
)
_DESCRIPTION_ATTR = re.compile(r'^(?!\s*(?:#|//))\s*description\s*=', re.MULTILINE)
_TYPE_ATTR = re.compile(r'^(?!\s*(?:#|//))\s*type\s*=', re.MULTILINE)
_RICH_TYPE = re.compile(
    r'^(?!\s*(?:#|//))\s*(?:.*\boptional\s*\(|validation\s*\{)', re.MULTILINE
)


def _variable_blocks(text: str) -> list[str]:
    """The body of each ``variable "x" { ... }`` block, with nested braces matched.

    Checking each block, rather than counting over the whole file, is what lets
    "every variable has a description and a type" actually be verified: a file
    total can be satisfied by one well-described variable (issue #54 review).
    """
    bodies = []
    for match in _VARIABLE_OPEN.finditer(text):
        depth, i = 1, match.end()
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        bodies.append(text[match.end() : i - 1])
    return bodies


def _variable_design(tf_files: list[Path]) -> CategoryScore:
    var_files = [p for p in tf_files if p.name == "variables.tf"]
    if not var_files:
        return _score("variable", MISSING, ["no variables.tf found"])
    blocks = [b for p in var_files for b in _variable_blocks(_code(p))]
    if not blocks:
        return _score("variable", MISSING, ["variables.tf present but declares no variables"])

    described = sum(1 for b in blocks if _DESCRIPTION_ATTR.search(b))
    typed = sum(1 for b in blocks if _TYPE_ATTR.search(b))
    evidence = [
        f"{len(blocks)} variable(s) across {len(var_files)} file(s): "
        f"{described} described, {typed} typed"
    ]
    if any(_RICH_TYPE.search(b) for b in blocks):
        evidence.append("uses optional() or validation")
    # Adopted means what the remediation text asks for: every variable has both
    # a description and a type. optional()/validation are evidence, not a
    # requirement, since not every module needs an object type.
    if described == typed == len(blocks):
        return _score("variable", ADOPTED, evidence)
    if described or typed:
        return _score("variable", PARTIAL, evidence)
    return _score("variable", MISSING, evidence)


# Adopted needs most modules to carry their own native tests.
_TESTED_ADOPTED_RATIO = 0.8


def _testing(files: list[Path], modules: list[Path]) -> CategoryScore:
    native = [p for p in files if p.name.endswith(".tftest.hcl")]
    go_tests = [p for p in files if p.name.endswith("_test.go")]
    if not native and not go_tests:
        return _score("testing", MISSING, ["no .tftest.hcl or _test.go files found"])

    # Map tests to the modules they sit in: comparing a total test count with
    # the module count lets one heavily tested module stand in for several
    # untested ones (issue #54 review).
    covered = [m for m in modules if any(m in t.parents for t in native)]
    evidence = [f"{len(covered)}/{len(modules)} module(s) have their own .tftest.hcl"]
    if go_tests:
        evidence.append(f"{len(go_tests)} Go test file(s), not mapped to modules")
    if modules and len(covered) / len(modules) >= _TESTED_ADOPTED_RATIO:
        return _score("testing", ADOPTED, evidence)
    return _score("testing", PARTIAL, evidence)


def _orchestration(discovery: DiscoveryResult) -> CategoryScore:
    tool = discovery.orchestration_tool
    if not tool:
        # A plain-Terraform workspace has no orchestration layer to assess, so
        # the category is excluded and its weight redistributed.
        return _score(
            "orchestration", NOT_APPLICABLE, ["no orchestration tool in use"]
        )
    evidence = [f"{tool} detected"]
    if discovery.orchestration_dir:
        evidence.append(f"configs under {discovery.orchestration_dir}")
        return _score("orchestration", ADOPTED, evidence)
    return _score("orchestration", PARTIAL, evidence + ["no orchestration directory found"])


# What a pipeline must actually run for CI/CD to count as adopted.
_PLAN_STEPS = (
    "terraform plan",
    "terragrunt plan",
    "run-all plan",
    "terramate run",
    "pulumi preview",
    "terraform-plan",
    "tf plan",
)


def _cicd(
    discovery: DiscoveryResult,
    pipelines: list[Path],
    pipeline_text: str,
    ws: Path,
) -> CategoryScore:
    platform = discovery.ci_cd_platform
    if not platform and not pipelines:
        return _score("cicd", MISSING, ["no CI/CD platform detected"])
    label = platform if platform and platform != "Unknown" else "a pipeline directory"
    evidence = [f"{label} detected"]
    if not pipelines:
        return _score("cicd", PARTIAL, evidence + ["no pipeline definition files found"])
    evidence.append(f"{len(pipelines)} pipeline file(s)")
    # Atlantis plans on every pull request by design, so its config is enough.
    plans = any(step in pipeline_text for step in _PLAN_STEPS) or any(
        p.name == "atlantis.yaml" for p in pipelines
    )
    if plans:
        evidence.append("a pipeline runs a plan step")
        return _score("cicd", ADOPTED, evidence)
    # Any pipeline file used to score Adopted, whatever it ran (#54 review).
    return _score("cicd", PARTIAL, evidence + ["no plan step found in any pipeline"])


_SECURITY_FILES = (
    ".checkov.yml",
    ".checkov.yaml",
    "tfsec.yml",
    "tfsec.yaml",
    ".trivyignore",
    ".tflint.hcl",
    ".terrascan.toml",
)
# Most teams run these as pinned CI steps with no config file at all, so a
# config-file-only probe reports a false Missing (issue #54 review).
_SCANNERS = ("checkov", "tfsec", "trivy", "terrascan", "conftest", "regula", "tflint")
# The key is an identifier that *ends* in a sensitive word. A bare `\bpassword`
# never matched `admin_password` or `db_password`, because `_` is a word
# character and leaves no boundary before "password" (issue #54 review).
_SECRET_HINT = re.compile(
    r'^(?!\s*(?:#|//))[^\n]*\b[A-Za-z0-9_]*(password|passwd|secret|access_key|api_key|token)'
    r'\s*=\s*"[^"$\n]{8,}"',
    re.IGNORECASE | re.MULTILINE,
)
_PIPELINE_HINT = (".yml", ".yaml")


def _pipeline_files(files: list[Path], names: set[str], ws: Path) -> list[Path]:
    """Files that look like CI definitions, for scanning their step contents."""
    out = []
    for path in files:
        rel = _rel(path, ws)
        if path.suffix.lower() not in _PIPELINE_HINT:
            continue
        if (
            rel.startswith(".github/workflows/")
            or rel.endswith((".gitlab-ci.yml", ".gitlab-ci.yaml"))
            or "azure-pipelines" in path.name
            or rel.startswith("pipelines/")
            or path.name == "atlantis.yaml"
        ):
            out.append(path)
    return out


# Hardcoded values usually live in the value and config files, not in the
# module code, so scanning only .tf misses them (issue #54 review).
_SECRET_SCAN_SUFFIXES = (".tf", ".tfvars", ".hcl")


def _secret_scan_files(files: list[Path]) -> list[Path]:
    """Terraform, variable-value and Terragrunt files to scan for credentials.

    Native test files are skipped: a `.tftest.hcl` is expected to carry dummy
    values for its `variables {}` block, and they are not deployed.
    """
    return [
        p
        for p in files
        if (p.suffix in _SECRET_SCAN_SUFFIXES or p.name.endswith(".tfvars.json"))
        and not p.name.endswith(".tftest.hcl")
    ]


def _security(
    files: list[Path],
    basenames: set[str],
    scan_files: list[Path],
    pipeline_text: str,
    ws: Path,
) -> CategoryScore:
    tooling = sorted(basenames & set(_SECURITY_FILES))
    rego = [p for p in files if p.suffix == ".rego"]
    evidence = []
    if tooling:
        evidence.append("policy tooling: " + ", ".join(tooling))
    if rego:
        evidence.append(f"{len(rego)} OPA policy file(s)")

    # A scanner invoked from a pipeline counts as much as a config file.
    in_ci = sorted(name for name in _SCANNERS if name in pipeline_text)
    if in_ci:
        evidence.append("scanners in CI: " + ", ".join(in_ci))

    # Every file is scanned: a cap would let a credential late in a large
    # repository pass as Adopted.
    secret = _search_tf(scan_files, _SECRET_HINT)
    if secret:
        return _score(
            "security",
            MISSING,
            evidence
            + [f"a literal credential-shaped value appears in {_rel(secret[0], ws)}"],
        )
    if in_ci or (tooling and rego):
        return _score("security", ADOPTED, evidence)
    if tooling or rego:
        return _score("security", PARTIAL, evidence)
    return _score("security", MISSING, ["no policy or security scanning configuration found"])


_QUALITY_FILES = (".pre-commit-config.yaml", ".pre-commit-config.yml", ".tflint.hcl", ".editorconfig")


# Invocations that show a pipeline actually enforces formatting or linting.
_QUALITY_STEPS = ("fmt", "tflint", "pre-commit", "terraform validate", "terragrunt hclfmt")


def _code_quality(
    basenames: set[str], pipelines: list[Path], pipeline_text: str
) -> CategoryScore:
    found = sorted(basenames & set(_QUALITY_FILES))
    evidence = []
    if found:
        evidence.append("config: " + ", ".join(found))
    runs = sorted(step for step in _QUALITY_STEPS if step in pipeline_text)
    if runs:
        evidence.append("a pipeline runs: " + ", ".join(runs))
    # A config file plus any pipeline used to score Adopted, even when no
    # pipeline ran the formatter or linter at all (issue #54 review).
    if found and runs:
        return _score("code_quality", ADOPTED, evidence)
    if found or runs:
        return _score("code_quality", PARTIAL, evidence)
    return _score("code_quality", MISSING, ["no linter or formatter configuration found"])


_BACKEND_BLOCK = re.compile(r'^(?!\s*(?:#|//))\s*backend\s+"', re.MULTILINE)
_LOCAL_BACKEND = re.compile(r'^(?!\s*(?:#|//))\s*backend\s+"local"', re.MULTILINE)


_BACKEND_TYPE = re.compile(r'^(?!\s*(?:#|//))\s*backend\s+"([^"]+)"', re.MULTILINE)


def _state(tf_files: list[Path], ws: Path) -> CategoryScore:
    """Score state management from backends declared in root modules.

    Terraform ignores a ``backend`` block in a child module, so one under
    ``modules/`` must not earn Adopted while the deployable roots still use
    local state (issue #54 review).
    """
    roots = [p for p in tf_files if "modules" not in p.relative_to(ws).parts[:-1]]
    if tf_files and not roots:
        # Every Terraform directory is a reusable module: backends belong to
        # the callers, so there is no state here to manage.
        return _score(
            "state",
            NOT_APPLICABLE,
            ["module library: no root stack, so state belongs to the callers"],
        )
    backends = []
    for path in roots:
        for match in _BACKEND_TYPE.finditer(_code(path)):
            backends.append((path, match.group(1)))
    remote = [(p, t) for p, t in backends if t != "local"]
    if remote:
        path, kind = remote[0]
        return _score(
            "state", ADOPTED, [f'remote backend "{kind}" in {_rel(path, ws)}']
        )
    if backends:
        return _score("state", PARTIAL, ["only a local backend is configured"])
    in_modules = any(
        _BACKEND_TYPE.search(_code(p)) for p in tf_files if p not in roots
    )
    if in_modules:
        return _score(
            "state",
            PARTIAL,
            ["a backend is declared only inside a reusable module, where Terraform ignores it"],
        )
    return _score("state", MISSING, ["no state backend configuration found"])


# "test" is omitted deliberately: it collides with unit-test directories, which
# are not a promotion stage (issue #54 review).
_ENV_NAMES = {
    "dev",
    "development",
    "staging",
    "stage",
    "uat",
    "qa",
    "preprod",
    "prod",
    "production",
}


def _rollout(ws: Path, ignored: frozenset[str]) -> CategoryScore:
    """Score a promotion ladder: environment directories that are siblings.

    Siblings matter — `environments/{dev,staging,prod}` is a ladder, whereas a
    stray `stage/` beside an unrelated `prod/` elsewhere is not. Directories are
    walked rather than files, so an environment directory still counts before it
    has any Terraform in it.
    """
    by_parent: dict[str, set[str]] = {}
    for dirpath, dirnames, _ in os.walk(ws):
        dirnames[:] = [d for d in dirnames if d not in ignored]
        here = {d.lower() for d in dirnames if d.lower() in _ENV_NAMES}
        if here:
            by_parent.setdefault(_rel(Path(dirpath), ws) or ".", set()).update(here)
    if not by_parent:
        return _score("rollout", MISSING, ["no environment directories found"])
    parent, envs = max(by_parent.items(), key=lambda kv: (len(kv[1]), kv[0]))
    listed = ", ".join(sorted(envs))
    if len(envs) >= 3:
        return _score("rollout", ADOPTED, [f"environments under {parent}/: {listed}"])
    if len(envs) == 2:
        return _score("rollout", PARTIAL, [f"environments under {parent}/: {listed}"])
    return _score("rollout", PARTIAL, [f"only one environment directory: {listed}"])
