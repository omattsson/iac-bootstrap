"""Tests for the standalone maturity report mode (issue #54).

Covers the scoring model, the gap classification, both output formats, file
output, and the exit codes the CLI contract promises.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from bootstrap_iac.cli import main
from bootstrap_iac.discovery import DiscoveryResult, scan_workspace
from bootstrap_iac.maturity import (
    ADOPTED,
    CATEGORIES,
    MISSING,
    NOT_APPLICABLE,
    PARTIAL,
    CategoryScore,
    MaturityReport,
    assess,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _mature_workspace(root: Path) -> Path:
    """A workspace that adopts most practices, for a high score."""
    module = root / "modules" / "tf-module-storage"
    module.mkdir(parents=True)
    (module / "main.tf").write_text(
        'resource "azurerm_storage_account" "s" {\n'
        "  name = local.name\n"
        "  tags = merge(var.env_default_tags, var.tags)\n}\n"
    )
    (module / "variables.tf").write_text(
        'variable "prefix" {\n  description = "p"\n  type = string\n}\n'
        'variable "opts" {\n  description = "o"\n'
        '  type = object({ a = optional(string, "x") })\n}\n'
    )
    (module / "outputs.tf").write_text('output "name" { value = local.name }\n')
    (module / "versions.tf").write_text('terraform {\n  backend "azurerm" {}\n}\n')
    (module / "locals.tf").write_text('locals { name = "${var.prefix}-st" }\n')
    (module / "storage.tftest.hcl").write_text('run "naming" { command = plan }\n')
    (root / ".tflint.hcl").write_text('plugin "azurerm" {}\n')
    (root / ".pre-commit-config.yaml").write_text("repos: []\n")
    (root / "policy.rego").write_text("package x\n")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "plan.yml").write_text("on: pull_request\n")
    for env in ("dev", "staging", "prod"):
        (root / "environments" / env).mkdir(parents=True)
    return root


def _assess(root: Path, **kwargs):
    return assess(scan_workspace(root), root, **kwargs)


# --- scoring model -----------------------------------------------------------


def test_category_weights_match_the_report_template():
    """The weights must stay in step with references/maturity-report.md.tmpl."""
    template = (_REPO_ROOT / "references" / "maturity-report.md.tmpl").read_text(
        encoding="utf-8"
    )
    assert sum(weight for _, _, weight in CATEGORIES) == 100
    for _, title, weight in CATEGORIES:
        assert f"| {title} | {weight}% |" in template, (
            f"{title} ({weight}%) is not the template's weight"
        )


def test_status_points_follow_the_documented_model():
    full = CategoryScore("k", "K", 20, ADOPTED)
    half = CategoryScore("k", "K", 20, PARTIAL)
    none = CategoryScore("k", "K", 20, MISSING)
    excluded = CategoryScore("k", "K", 20, NOT_APPLICABLE)
    assert (full.points, half.points, none.points) == (20, 10, 0)
    assert excluded.points == 0


def test_na_categories_are_excluded_and_weights_renormalised():
    """N/A must not simply score zero: it leaves the total out of the divisor."""
    cats = [
        CategoryScore("a", "A", 50, ADOPTED),
        CategoryScore("b", "B", 30, ADOPTED),
        CategoryScore("c", "C", 20, NOT_APPLICABLE),
    ]
    report = MaturityReport(workspace=Path("."), categories=cats)
    assert report.available_points == 80
    # 80 of 80 applicable points, not 80 of 100.
    assert report.overall_score == 100


@pytest.mark.parametrize(
    "score, rating",
    [(100, "Strong"), (80, "Strong"), (79, "Developing"), (60, "Developing"),
     (59, "Foundational"), (40, "Foundational"), (39, "Early"), (0, "Early")],
)
def test_rating_bands_match_the_template(score, rating):
    """Exercise MaturityReport.rating exactly on each band boundary.

    An adopted category of weight `score` plus a missing one of the remainder
    yields precisely that percentage.
    """
    cats = [CategoryScore("a", "A", score, ADOPTED)] if score else []
    if score < 100:
        cats.append(CategoryScore("b", "B", 100 - score, MISSING))
    report = MaturityReport(workspace=Path("."), categories=cats)
    assert report.overall_score == score
    assert rating in report.rating


def test_gap_classification_splits_critical_from_moderate():
    """Missing is always critical; Partial is critical only at weight >= 15."""
    cats = [
        CategoryScore("security", "Security", 20, PARTIAL),   # heavy partial
        CategoryScore("state", "State Management", 5, PARTIAL),  # light partial
        CategoryScore("naming", "Naming & Tagging", 10, MISSING),  # any missing
        CategoryScore("testing", "Testing", 15, ADOPTED),
    ]
    report = MaturityReport(workspace=Path("."), categories=cats)
    assert [c.key for c in report.critical_gaps] == ["security", "naming"]
    assert [c.key for c in report.moderate_gaps] == ["state"]
    assert [c.key for c in report.strengths] == ["testing"]


# --- assessment against real workspaces --------------------------------------


def test_bare_workspace_scores_zero_and_flags_every_category(tmp_path):
    report = _assess(tmp_path)
    assert report.overall_score == 0
    assert "Early" in report.rating
    assert not report.strengths
    # Orchestration is N/A for a plain workspace, so it is not a gap.
    assert "orchestration" not in [c.key for c in report.critical_gaps]


def test_mature_workspace_scores_highly_with_evidence(tmp_path):
    report = _assess(_mature_workspace(tmp_path))
    assert report.overall_score >= 80, report.to_dict()
    assert "Strong" in report.rating
    by_key = {c.key: c for c in report.categories}
    for key in ("module_design", "testing", "cicd", "security", "state", "rollout"):
        assert by_key[key].status == ADOPTED, f"{key} not adopted"
        assert by_key[key].evidence, f"{key} scored without evidence"


def test_orchestration_is_not_applicable_without_a_tool(tmp_path):
    """A plain-Terraform workspace has no orchestration layer to assess."""
    (tmp_path / "main.tf").write_text('resource "x" "y" {}\n')
    report = _assess(tmp_path)
    orch = next(c for c in report.categories if c.key == "orchestration")
    assert orch.status == NOT_APPLICABLE
    assert report.available_points == 95


def test_hardcoded_credential_forces_security_to_missing(tmp_path):
    """Configured tooling must not mask a literal credential in the code."""
    (tmp_path / ".tflint.hcl").write_text("plugin {}\n")
    (tmp_path / "policy.rego").write_text("package x\n")
    (tmp_path / "main.tf").write_text(
        'resource "x" "y" {\n  client_secret = "s3cr3t-value-not-a-var"\n}\n'
    )
    report = _assess(tmp_path)
    security = next(c for c in report.categories if c.key == "security")
    assert security.status == MISSING
    assert any("credential" in e for e in security.evidence)


def test_assessment_writes_nothing_into_the_workspace(tmp_path):
    """The mode is read-only: evaluating a workspace must not modify it."""
    _mature_workspace(tmp_path)
    before = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")}
    _assess(tmp_path).render(templates_dir=_REPO_ROOT / "references")
    after = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")}
    assert before == after


# --- rendering ---------------------------------------------------------------


def test_markdown_render_resolves_every_placeholder(tmp_path):
    report = _assess(_mature_workspace(tmp_path))
    rendered = report.render(templates_dir=_REPO_ROOT / "references")
    assert "{{" not in rendered, "unresolved placeholder in the rendered report"
    assert str(report.overall_score) in rendered
    assert report.rating in rendered


def test_json_output_is_machine_readable(tmp_path):
    report = _assess(_mature_workspace(tmp_path))
    data = json.loads(report.to_json())
    assert data["overall_score"] == report.overall_score
    assert len(data["categories"]) == len(CATEGORIES)
    assert {"key", "title", "weight", "status", "points", "evidence"} <= set(
        data["categories"][0]
    )
    assert isinstance(data["recommended_actions"], list)


def test_recommended_actions_are_ordered_by_severity_then_weight(tmp_path):
    cats = [
        CategoryScore("state", "State Management", 5, PARTIAL),     # moderate
        CategoryScore("security", "Security", 20, MISSING),          # critical, heaviest
        CategoryScore("cicd", "CI/CD", 15, MISSING),                 # critical
    ]
    report = MaturityReport(workspace=Path("."), categories=cats)
    actions = report.recommended_actions()
    assert actions[0].startswith("Security")
    assert actions[1].startswith("CI/CD")
    assert actions[2].startswith("State Management")


# --- CLI contract ------------------------------------------------------------


def test_cli_prints_markdown_and_exits_zero(tmp_path):
    result = CliRunner().invoke(
        main, ["--maturity-report", "--workspace", str(_mature_workspace(tmp_path))]
    )
    assert result.exit_code == 0, result.output
    assert "IaC Maturity Assessment" in result.output
    assert "{{" not in result.output


def test_cli_json_format(tmp_path):
    result = CliRunner().invoke(
        main,
        ["--maturity-report", "--workspace", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "overall_score" in data and "categories" in data


def test_cli_writes_to_a_file_and_keeps_stdout_clean(tmp_path):
    out = tmp_path / "out" / "maturity.md"
    result = CliRunner().invoke(
        main,
        [
            "--maturity-report",
            "--workspace",
            str(tmp_path),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    assert "IaC Maturity Assessment" in out.read_text(encoding="utf-8")


def test_cli_threshold_controls_the_exit_code(tmp_path):
    ws = str(_mature_workspace(tmp_path))
    runner = CliRunner()
    above = runner.invoke(
        main, ["--maturity-report", "--workspace", ws, "--maturity-threshold", "10"]
    )
    assert above.exit_code == 0
    below = runner.invoke(
        main, ["--maturity-report", "--workspace", ws, "--maturity-threshold", "100"]
    )
    assert below.exit_code == 1


def test_cli_without_a_threshold_never_fails_on_a_low_score(tmp_path):
    """Gating is opt-in, so a bare report of a poor workspace still exits 0."""
    result = CliRunner().invoke(
        main, ["--maturity-report", "--workspace", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0
    # Assert the score itself. Bare "0%" also appears in the template's static
    # scoring-methodology text, so it passes for any report (issue #54 review).
    assert json.loads(result.output)["overall_score"] == 0


def test_cli_reports_a_missing_workspace(tmp_path):
    result = CliRunner().invoke(
        main, ["--maturity-report", "--workspace", str(tmp_path / "nope")]
    )
    assert result.exit_code == 2


def test_cli_uses_the_supplied_company_name(tmp_path):
    result = CliRunner().invoke(
        main,
        ["--maturity-report", "--workspace", str(tmp_path), "--company", "Acme Corp"],
    )
    assert result.exit_code == 0
    assert "Acme Corp" in result.output


def test_cli_generates_no_files_in_the_workspace(tmp_path):
    """--maturity-report must not write agent or instruction files.

    Run against a populated workspace and compare relative paths: an empty
    directory makes the comparison trivially true (issue #54 review).
    """
    ws = _mature_workspace(tmp_path)
    before = {p.relative_to(ws).as_posix() for p in ws.rglob("*")}
    assert before, "fixture is empty, so this would not prove anything"
    result = CliRunner().invoke(main, ["--maturity-report", "--workspace", str(ws)])
    assert result.exit_code == 0
    after = {p.relative_to(ws).as_posix() for p in ws.rglob("*")}
    assert before == after
    assert not (ws / "CLAUDE.md").exists()
    assert not (ws / ".claude").exists()


# --- regressions from the pre-commit review -----------------------------------


def test_secret_is_found_beyond_any_file_cap(tmp_path):
    """A credential late in a large repository must not pass as Adopted.

    The first implementation concatenated only the first 400 .tf files, so a
    monorepo could report Security 20/20 with a hardcoded secret (#54 review).
    """
    for i in range(420):
        (tmp_path / f"m{i:04d}.tf").write_text('resource "x" "y" {}\n')
    (tmp_path / ".tflint.hcl").write_text("plugin {}\n")
    (tmp_path / "policy.rego").write_text("package x\n")
    (tmp_path / "zzz_last.tf").write_text(
        'resource "a" "b" {\n  client_secret = "hardcoded-real-secret-1234"\n}\n'
    )
    security = next(c for c in _assess(tmp_path).categories if c.key == "security")
    assert security.status == MISSING
    assert any("zzz_last.tf" in e for e in security.evidence)


def test_scanner_wired_into_ci_counts_without_a_config_file(tmp_path):
    """Most teams run checkov or tfsec as a pinned CI step with no config."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "tf.yml").write_text(
        "jobs:\n  scan:\n    steps:\n      - uses: bridgecrewio/checkov-action@v12\n"
    )
    security = next(c for c in _assess(tmp_path).categories if c.key == "security")
    assert security.status == ADOPTED
    assert any("checkov" in e for e in security.evidence)


def test_commented_out_credential_is_not_a_finding(tmp_path):
    """A commented example must not be reported as a hardcoded credential."""
    (tmp_path / ".tflint.hcl").write_text("plugin {}\n")
    (tmp_path / "policy.rego").write_text("package x\n")
    (tmp_path / "main.tf").write_text(
        'resource "x" "y" {\n  # password = "changeme-in-production"\n}\n'
    )
    security = next(c for c in _assess(tmp_path).categories if c.key == "security")
    assert security.status == ADOPTED
    assert not any("credential" in e for e in security.evidence)


def test_description_must_be_an_attribute_not_a_word(tmp_path):
    """Counting the word "description" let a file with none score full marks."""
    (tmp_path / "variables.tf").write_text(
        'variable "a" {\n  # description of a\n  type = string\n'
        '  default = "see description below"\n}\n'
        'variable "b" { type = string }\n'
    )
    variable = next(c for c in _assess(tmp_path).categories if c.key == "variable")
    assert variable.status == MISSING
    assert any("0 description" in e for e in variable.evidence)


def test_module_design_needs_a_real_majority(tmp_path):
    """One complete module out of three is not Adopted."""
    for name, full in (("a", True), ("b", False), ("c", False)):
        d = tmp_path / "modules" / name
        d.mkdir(parents=True)
        (d / "main.tf").write_text("x")
        if full:
            (d / "variables.tf").write_text("x")
            (d / "outputs.tf").write_text("x")
    module = next(c for c in _assess(tmp_path).categories if c.key == "module_design")
    assert module.status == PARTIAL
    assert any("1/3" in e for e in module.evidence)


def test_environment_stacks_are_not_counted_as_modules(tmp_path):
    """A root stack is a caller: it needs no outputs.tf and no test of its own."""
    module = tmp_path / "modules" / "net"
    module.mkdir(parents=True)
    for f in ("main.tf", "variables.tf", "outputs.tf"):
        (module / f).write_text("x")
    (module / "net.tftest.hcl").write_text('run "a" { command = plan }\n')
    for env in ("dev", "staging", "prod"):
        e = tmp_path / "environments" / env
        e.mkdir(parents=True)
        (e / "main.tf").write_text('module "n" { source = "../../modules/net" }\n')
    by_key = {c.key: c for c in _assess(tmp_path).categories}
    assert by_key["module_design"].status == ADOPTED
    assert by_key["testing"].status == ADOPTED


def test_backend_attribute_is_not_a_backend_block(tmp_path):
    """`backend_address_pool` is an everyday attribute, not state configuration."""
    (tmp_path / "main.tf").write_text(
        'resource "azurerm_application_gateway" "g" {\n'
        '  backend_address_pool { name = "p" }\n}\n'
    )
    state = next(c for c in _assess(tmp_path).categories if c.key == "state")
    assert state.status == MISSING


def test_a_pipelines_named_module_is_not_a_pipeline(tmp_path):
    """`modules/data-pipelines/` must not count as CI being present."""
    (tmp_path / ".editorconfig").write_text("root=true\n")
    d = tmp_path / "modules" / "data-pipelines"
    d.mkdir(parents=True)
    (d / "main.tf").write_text("x")
    quality = next(c for c in _assess(tmp_path).categories if c.key == "code_quality")
    assert quality.status == PARTIAL
    assert not any("pipeline is present" in e for e in quality.evidence)


def test_unit_test_directory_is_not_an_environment(tmp_path):
    """A `test/` directory is not a promotion stage, and stray dirs are not siblings."""
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "README.md").write_text("x")
    (tmp_path / "modules" / "stage").mkdir(parents=True)
    rollout = next(c for c in _assess(tmp_path).categories if c.key == "rollout")
    assert rollout.status == PARTIAL
    assert not any("test" in e for e in rollout.evidence)


def test_orchestration_is_scored_when_a_tool_is_present(tmp_path):
    """The tool-present branch of the orchestration probe."""
    live = tmp_path / "live" / "dev"
    live.mkdir(parents=True)
    (live / "terragrunt.hcl").write_text('include "root" {}\n')
    (tmp_path / "terragrunt.hcl").write_text("locals {}\n")
    report = _assess(tmp_path)
    orch = next(c for c in report.categories if c.key == "orchestration")
    assert orch.status in (ADOPTED, PARTIAL)
    assert report.available_points == 100, "orchestration should no longer be N/A"


def test_threshold_compares_the_unrounded_score():
    """79.5% must not pass a threshold of 80 just because display rounds up."""
    cats = [
        CategoryScore("a", "A", 79, ADOPTED),
        CategoryScore("b", "B", 1, PARTIAL),
        CategoryScore("c", "C", 20, MISSING),
    ]
    report = MaturityReport(workspace=Path("."), categories=cats)
    assert report.score_exact == pytest.approx(79.5)
    assert report.overall_score == 80  # display rounds
    assert report.score_exact < 80  # gating does not


def test_a_fifo_in_the_workspace_does_not_block(tmp_path):
    """Reading a non-regular file would hang the assessment."""
    if not hasattr(os, "mkfifo"):  # pragma: no cover - POSIX only
        pytest.skip("mkfifo unavailable")
    (tmp_path / "main.tf").write_text('resource "x" "y" {}\n')
    os.mkfifo(tmp_path / "pipe.tf")
    # Assess with a plain DiscoveryResult: scan_workspace() reads the FIFO and
    # blocks, which is a pre-existing discovery issue (it affects --discover
    # too) and is not what this test is about.
    report = assess(DiscoveryResult(workspace_path=tmp_path), tmp_path)
    assert report.overall_score >= 0


@pytest.mark.parametrize(
    "args", [["--output", "x.md"], ["--format", "json"], ["--maturity-threshold", "50"]]
)
def test_maturity_flags_require_the_mode(tmp_path, args):
    """Silently ignoring --output on a generating tool would be a trap."""
    result = CliRunner().invoke(main, ["--workspace", str(tmp_path)] + args)
    assert result.exit_code == 2
    assert "requires --maturity-report" in result.output


def test_discover_and_maturity_report_conflict(tmp_path):
    result = CliRunner().invoke(
        main, ["--discover", "--maturity-report", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "cannot be combined" in result.output


def test_report_definitions_match_the_implementation(tmp_path):
    """The rendered document must not argue with its own printed definitions."""
    rendered = _assess(tmp_path).render(templates_dir=_REPO_ROOT / "references")
    assert "weighted 15% or more" in rendered
    assert "A Partial status in a category weighted under 15%." in rendered
    # The superseded wording, which contradicted the code, must be gone.
    assert "Partial or Missing status in categories other than" not in rendered


def test_output_mode_leaves_stdout_empty_for_redirection(tmp_path):
    """Run the real process: CliRunner folds stderr into stdout on older Click,
    so only separate pipes prove the streams are actually split (#54 review).
    """
    import subprocess
    import sys

    out = tmp_path / "maturity.md"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_REPO_ROOT / "cli") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "bootstrap_iac",
            "--maturity-report",
            "--workspace",
            str(tmp_path),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "", f"stdout not clean: {proc.stdout!r}"
    # The one-line summary goes to stderr instead.
    assert "Maturity report written" in proc.stderr
    assert out.is_file()
