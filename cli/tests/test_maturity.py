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
    # A reusable module pins versions but declares no backend: Terraform ignores
    # a backend in a child module, so it belongs in the root stacks below.
    (module / "versions.tf").write_text('terraform {\n  required_version = ">= 1.5"\n}\n')
    (module / "locals.tf").write_text('locals { name = "${var.prefix}-st" }\n')
    (module / "storage.tftest.hcl").write_text('run "naming" { command = plan }\n')
    (root / ".tflint.hcl").write_text('plugin "azurerm" {}\n')
    (root / ".pre-commit-config.yaml").write_text("repos: []\n")
    (root / "policy.rego").write_text("package x\n")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "plan.yml").write_text(
        "on: pull_request\n"
        "jobs:\n  plan:\n    steps:\n"
        "      - run: terraform fmt -check -recursive\n"
        "      - run: tflint --recursive\n"
        "      - run: terraform plan -out=tfplan\n"
    )
    # Each environment is a root stack that calls the module and owns its state.
    for env in ("dev", "staging", "prod"):
        stack = root / "environments" / env
        stack.mkdir(parents=True)
        (stack / "main.tf").write_text(
            'module "storage" {\n  source = "../../modules/tf-module-storage"\n}\n'
        )
        (stack / "backend.tf").write_text('terraform {\n  backend "azurerm" {}\n}\n')
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


def test_gap_classification_follows_skill_md():
    """SKILL.md: any Missing is critical; a Partial is critical only in Security,
    Testing or CI/CD. Module Design is Partial-moderate despite its 15% weight,
    so the discriminator is category membership, not weight (#54 review)."""
    cats = [
        CategoryScore("security", "Security", 20, PARTIAL),        # critical
        CategoryScore("module_design", "Module Design", 15, PARTIAL),  # moderate, not weight
        CategoryScore("state", "State Management", 5, PARTIAL),    # moderate
        CategoryScore("naming", "Naming & Tagging", 10, MISSING),  # any Missing is critical
        CategoryScore("testing", "Testing", 15, ADOPTED),
    ]
    report = MaturityReport(workspace=Path("."), categories=cats)
    assert [c.key for c in report.critical_gaps] == ["security", "naming"]
    assert [c.key for c in report.moderate_gaps] == ["module_design", "state"]
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
    # The word "description" in a comment and a default string earns nothing.
    assert any("0 described" in e for e in variable.evidence), variable.evidence
    # The variables are typed, so this is Partial rather than Missing, but it
    # must never be Adopted.
    assert variable.status != ADOPTED


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


def test_display_rating_and_gating_share_one_score():
    """A 79.5 must print, rate and gate as the same number.

    Integer display with exact rating printed "80%" beside a Developing rating;
    integer gating let 79.5 pass a threshold of 80 (issue #54 review).
    """
    cats = [
        CategoryScore("module_design", "Module Design", 79, ADOPTED),
        CategoryScore("naming", "Naming & Tagging", 1, PARTIAL),
        CategoryScore("testing", "Testing", 20, MISSING),
    ]
    report = MaturityReport(workspace=Path("."), categories=cats)
    assert report.overall_score == pytest.approx(79.5)
    assert report.display_score == "79.5"
    assert "Developing" in report.rating
    assert report.overall_score < 80  # so a threshold of 80 fails


def test_whole_scores_display_without_a_decimal():
    cats = [CategoryScore("module_design", "Module Design", 100, ADOPTED)]
    assert MaturityReport(workspace=Path("."), categories=cats).display_score == "100"


def test_total_row_is_normalised_when_a_category_is_na():
    """All adopted with Orchestration N/A must read 100% and 100/100, not 95/100."""
    cats = [
        CategoryScore(k, t, w, NOT_APPLICABLE if k == "orchestration" else ADOPTED)
        for k, t, w in CATEGORIES
    ]
    ctx = MaturityReport(workspace=Path("."), categories=cats).context()
    assert ctx["OVERALL_SCORE"] == "100"
    assert ctx["OVERALL_SCORE_POINTS"] == "100"


def test_cli_gates_on_the_score_it_displays(tmp_path):
    """Exercise the CLI comparison itself, not only the model property.

    The previous test checked `score_exact` on the model while the CLI still
    compared the rounded integer, so it passed with the bug in place.
    """
    ws = _mature_workspace(tmp_path)
    runner = CliRunner()
    data = json.loads(
        runner.invoke(main, ["--maturity-report", "--workspace", str(ws), "--format", "json"]).output
    )
    score = data["overall_score"]
    at = runner.invoke(
        main, ["--maturity-report", "--workspace", str(ws), "--maturity-threshold", str(int(score))]
    )
    assert at.exit_code == 0, f"score {score} should pass a threshold of {int(score)}"
    above = int(score) + 1
    if above <= 100:
        over = runner.invoke(
            main, ["--maturity-report", "--workspace", str(ws), "--maturity-threshold", str(above)]
        )
        assert over.exit_code == 1, f"score {score} should fail a threshold of {above}"


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
    assert "a Partial status in Security, Testing, or CI/CD." in rendered
    assert "A Partial status in any other category, including Module Design." in rendered
    # Superseded wordings that contradicted the code or SKILL.md must be gone.
    assert "Partial or Missing status in categories other than" not in rendered
    assert "weighted 15% or more" not in rendered


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


# --- regressions from the Copilot review on PR #74 ---------------------------


@pytest.mark.parametrize(
    "mode_args",
    [["--validate", "."], ["--check-config"], ["--discover"]],
)
def test_every_exclusive_mode_conflicts_with_maturity_report(tmp_path, mode_args):
    """--validate and --check-config used to exit before the conflict check,
    so combining them with --maturity-report silently ran the other mode."""
    result = CliRunner().invoke(
        main, mode_args + ["--maturity-report", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "cannot be combined" in result.output
    # No report was produced by whichever mode happened to run first.
    assert "IaC Maturity Assessment" not in result.output


def test_untyped_variables_are_not_adopted(tmp_path):
    """Descriptions plus one validation used to earn Adopted with no types."""
    (tmp_path / "variables.tf").write_text(
        'variable "a" {\n  description = "a"\n'
        "  validation {\n    condition = length(var.a) > 0\n"
        '    error_message = "empty"\n  }\n}\n'
        'variable "b" {\n  description = "b"\n}\n'
    )
    variable = next(c for c in _assess(tmp_path).categories if c.key == "variable")
    assert variable.status == PARTIAL
    assert any("0 typed" in e for e in variable.evidence), variable.evidence


def test_one_documented_variable_does_not_cover_the_others(tmp_path):
    """Per-block checks: a file total could be met by a single variable."""
    (tmp_path / "variables.tf").write_text(
        'variable "a" {\n  description = "a"\n  type = string\n}\n'
        'variable "b" {}\n'
    )
    variable = next(c for c in _assess(tmp_path).categories if c.key == "variable")
    assert variable.status == PARTIAL


@pytest.mark.parametrize(
    "name, body",
    [
        ("prod.tfvars", 'admin_password = "hunter2-real-value"\n'),
        ("terragrunt.hcl", 'inputs = {\n  client_secret = "hunter2-real-value"\n}\n'),
    ],
)
def test_credentials_in_value_and_config_files_are_found(tmp_path, name, body):
    """Hardcoded values usually live in .tfvars or Terragrunt .hcl, not in .tf."""
    (tmp_path / ".tflint.hcl").write_text("plugin {}\n")
    (tmp_path / "policy.rego").write_text("package x\n")
    (tmp_path / name).write_text(body)
    security = next(c for c in _assess(tmp_path).categories if c.key == "security")
    assert security.status == MISSING
    assert any(name in e for e in security.evidence), security.evidence


def test_test_fixture_dummy_values_are_not_credentials(tmp_path):
    """A .tftest.hcl is expected to carry dummy values, and is not deployed."""
    (tmp_path / ".tflint.hcl").write_text("plugin {}\n")
    (tmp_path / "policy.rego").write_text("package x\n")
    (tmp_path / "m.tftest.hcl").write_text(
        'variables {\n  admin_password = "not-a-real-password"\n}\n'
    )
    security = next(c for c in _assess(tmp_path).categories if c.key == "security")
    assert security.status == ADOPTED


def test_backend_in_a_child_module_is_not_state_management(tmp_path):
    """Terraform ignores a backend in a child module, so it must not earn Adopted."""
    module = tmp_path / "modules" / "net"
    module.mkdir(parents=True)
    (module / "main.tf").write_text('terraform {\n  backend "azurerm" {}\n}\n')
    stack = tmp_path / "environments" / "prod"
    stack.mkdir(parents=True)
    (stack / "main.tf").write_text('module "n" { source = "../../modules/net" }\n')
    state = next(c for c in _assess(tmp_path).categories if c.key == "state")
    assert state.status == PARTIAL
    assert any("reusable module" in e for e in state.evidence), state.evidence


def test_a_pure_module_library_has_no_state_to_manage(tmp_path):
    """Backends belong to the callers, so a module-only repo is N/A, not Missing."""
    module = tmp_path / "modules" / "net"
    module.mkdir(parents=True)
    (module / "main.tf").write_text('resource "x" "y" {}\n')
    state = next(c for c in _assess(tmp_path).categories if c.key == "state")
    assert state.status == NOT_APPLICABLE


def test_a_pipeline_file_alone_is_not_adopted_cicd(tmp_path):
    """Any pipeline file used to score Adopted, whatever it ran."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "lint.yml").write_text("on: push\njobs:\n  x:\n    steps:\n      - run: echo hi\n")
    cicd = next(c for c in _assess(tmp_path).categories if c.key == "cicd")
    assert cicd.status == PARTIAL
    assert any("no plan step" in e for e in cicd.evidence)


def test_code_quality_needs_ci_to_run_the_linter(tmp_path):
    """A config file plus an unrelated pipeline is not enforcement."""
    (tmp_path / ".tflint.hcl").write_text("plugin {}\n")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "deploy.yml").write_text("on: push\njobs:\n  x:\n    steps:\n      - run: echo hi\n")
    quality = next(c for c in _assess(tmp_path).categories if c.key == "code_quality")
    assert quality.status == PARTIAL


def test_tests_must_cover_modules_not_just_outnumber_them(tmp_path):
    """Two tests in one module must not stand in for an untested second module."""
    for name in ("a", "b"):
        d = tmp_path / "modules" / name
        d.mkdir(parents=True)
        (d / "main.tf").write_text('resource "x" "y" {}\n')
    (tmp_path / "modules" / "a" / "one.tftest.hcl").write_text('run "1" { command = plan }\n')
    (tmp_path / "modules" / "a" / "two.tftest.hcl").write_text('run "2" { command = plan }\n')
    testing = next(c for c in _assess(tmp_path).categories if c.key == "testing")
    assert testing.status == PARTIAL
    assert any("1/2 module(s)" in e for e in testing.evidence), testing.evidence


# --- regressions from the second Copilot review on PR #74 --------------------


def test_severity_model_agrees_across_skill_template_readme_and_code():
    """Bootstrap and --maturity-report must classify the same assessment the
    same way, so every document names the same critical-if-Partial set."""
    from bootstrap_iac.maturity import _CRITICAL_IF_PARTIAL

    assert _CRITICAL_IF_PARTIAL == {"security", "testing", "cicd"}
    skill = (_REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    template = (_REPO_ROOT / "references" / "maturity-report.md.tmpl").read_text(encoding="utf-8")
    readme = (_REPO_ROOT / "cli" / "README.md").read_text(encoding="utf-8")
    for doc, name in ((skill, "SKILL.md"), (template, "template"), (readme, "README")):
        flat = " ".join(doc.split())
        assert "Partial status in Security, Testing, or CI/CD" in flat or (
            "Partial in Security, Testing or CI/CD" in flat
        ), f"{name} does not name the critical-if-Partial categories"
        assert "including Module Design" in flat, f"{name} does not keep Module Design moderate"
        # No document may list Module Design among the critical categories.
        assert "(Module Design, Testing, CI/CD, Security)" not in flat, name


def test_explicit_markdown_format_still_requires_the_mode(tmp_path):
    """`--format markdown` used to look identical to the default and slip through."""
    result = CliRunner().invoke(
        main, ["--workspace", str(tmp_path), "--format", "markdown"]
    )
    assert result.exit_code == 2
    assert "--format" in result.output and "requires --maturity-report" in result.output


def test_markdown_is_still_the_default_format(tmp_path):
    result = CliRunner().invoke(main, ["--maturity-report", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("# IaC Maturity Assessment")


def test_braces_inside_strings_do_not_end_a_variable_block(tmp_path):
    """`default = "}"` before the description and type must not close the block."""
    (tmp_path / "variables.tf").write_text(
        'variable "suffix" {\n'
        '  default     = "}"\n'
        '  description = "closing brace is data, not structure"\n'
        "  type        = string\n"
        "}\n"
        'variable "tpl" {\n'
        '  default     = "${join("}", ["a"])} # not a comment"\n'
        '  description = "template with a nested quoted brace"\n'
        "  type        = string\n"
        "}\n"
        'variable "doc" {\n'
        "  default     = <<-EOT\n"
        "    { not: structure }\n"
        "  EOT\n"
        '  description = "heredoc containing braces"\n'
        "  type        = string\n"
        "}\n"
    )
    variable = next(c for c in _assess(tmp_path).categories if c.key == "variable")
    assert variable.status == ADOPTED, variable.evidence
    assert any("3 variable(s)" in e and "3 described, 3 typed" in e for e in variable.evidence)


def test_line_comment_braces_do_not_end_a_variable_block(tmp_path):
    (tmp_path / "variables.tf").write_text(
        'variable "a" {\n'
        "  # } this brace is in a comment\n"
        '  description = "a"\n'
        "  type        = string\n"
        "}\n"
    )
    variable = next(c for c in _assess(tmp_path).categories if c.key == "variable")
    assert variable.status == ADOPTED, variable.evidence


def test_credentials_in_tfvars_json_are_found(tmp_path):
    """.tfvars.json uses a quoted key and a colon, which the HCL pattern missed."""
    (tmp_path / ".tflint.hcl").write_text("plugin {}\n")
    (tmp_path / "policy.rego").write_text("package x\n")
    (tmp_path / "prod.tfvars.json").write_text('{"admin_password": "hardcoded-value-123"}\n')
    security = next(c for c in _assess(tmp_path).categories if c.key == "security")
    assert security.status == MISSING
    assert any("prod.tfvars.json" in e for e in security.evidence), security.evidence


def test_cloud_block_is_remote_state(tmp_path):
    """Terraform Cloud / Enterprise uses `cloud {}` rather than a backend block."""
    (tmp_path / "main.tf").write_text(
        'terraform {\n  cloud {\n    organization = "acme"\n'
        '    workspaces { name = "prod" }\n  }\n}\n'
    )
    state = next(c for c in _assess(tmp_path).categories if c.key == "state")
    assert state.status == ADOPTED
    assert any("cloud" in e.lower() for e in state.evidence), state.evidence


def test_cloud_block_in_a_child_module_is_still_ignored(tmp_path):
    module = tmp_path / "modules" / "net"
    module.mkdir(parents=True)
    (module / "main.tf").write_text('terraform {\n  cloud {\n    organization = "x"\n  }\n}\n')
    (tmp_path / "main.tf").write_text('module "n" { source = "./modules/net" }\n')
    state = next(c for c in _assess(tmp_path).categories if c.key == "state")
    assert state.status == PARTIAL
    assert any("reusable module" in e for e in state.evidence)
