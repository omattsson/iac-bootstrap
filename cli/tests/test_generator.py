"""Tests for bootstrap_iac.generator."""

import pytest
import stat
import os
from pathlib import Path

import bootstrap_iac.generator as generator_module
from bootstrap_iac.generator import (
    GenerationError, OutputSpec, resolve_placeholders, generate_files, get_templates_dir,
    _cloud_template, _build_output_specs,
)
from bootstrap_iac.interview import build_context


# ---------------------------------------------------------------------------
# resolve_placeholders
# ---------------------------------------------------------------------------


def test_resolve_simple_placeholders():
    content = "Hello {{COMPANY_NAME}}, welcome to {{CLOUD_PROVIDER}}!"
    ctx = {"COMPANY_NAME": "Acme", "CLOUD_PROVIDER": "Azure"}
    result = resolve_placeholders(content, ctx)
    assert result == "Hello Acme, welcome to Azure!"


def test_resolve_unknown_placeholder_left_intact():
    content = "Value: {{UNKNOWN_KEY}}"
    result = resolve_placeholders(content, {})
    assert result == "Value: {{UNKNOWN_KEY}}"


def test_resolve_no_placeholders():
    content = "No placeholders here."
    result = resolve_placeholders(content, {"X": "y"})
    assert result == "No placeholders here."


def test_resolve_repeated_placeholder():
    content = "{{X}} and {{X}} again"
    result = resolve_placeholders(content, {"X": "hello"})
    assert result == "hello and hello again"


def test_resolve_empty_value():
    content = "prefix-{{EMPTY}}-suffix"
    result = resolve_placeholders(content, {"EMPTY": ""})
    assert result == "prefix--suffix"


def test_resolve_multiline_value():
    content = "Standards:\n{{STANDARD_VARIABLES}}"
    ctx = {"STANDARD_VARIABLES": "- prefix\n- location"}
    result = resolve_placeholders(content, ctx)
    assert "- prefix" in result
    assert "- location" in result


# ---------------------------------------------------------------------------
# build_context derives expected keys
# ---------------------------------------------------------------------------


def test_build_context_azure_defaults():
    answers = {
        "COMPANY_NAME": "Contoso",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": "Terragrunt",
        "ORCHESTRATION_DIR": "infra-config",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "Managed Identity / OIDC",
        "STATE_BACKEND": "Azure Blob Storage",
        "NAMING_PATTERN": "{prefix}-{type}-{suffix}",
        "TAG_STRATEGY": "merge(var.env_default_tags, var.tags)",
        "STANDARD_VARIABLES": "- prefix\n- location",
        "TARGET": "both",
        "ORG": "contoso",
    }
    ctx = build_context(answers)

    assert ctx["PROVIDER_NAME"] == "azurerm"
    assert "azurerm" in ctx["PROVIDER_BLOCK"]
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terragrunt"
    assert ctx["VALIDATE_COMMAND"] == "terragrunt validate"
    assert ctx["PLAN_COMMAND"] == "terragrunt plan"
    assert ctx["PIPELINE_APPLY_TO"] == ".github/workflows/**/*.yml"
    assert "contoso" in ctx["MODULE_SOURCE_PATTERN"]
    assert "tf-module" in ctx["MODULE_SOURCE_PATTERN"]


def test_build_context_aws_defaults():
    answers = {
        "COMPANY_NAME": "ACME",
        "CLOUD_PROVIDER": "AWS",
        "MODULE_PREFIX": "terraform-aws",
        "ORCHESTRATION_TOOL": "None",
        "ORCHESTRATION_DIR": ".",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "IAM Roles via OIDC",
        "STATE_BACKEND": "S3",
        "NAMING_PATTERN": "{prefix}-{type}",
        "TAG_STRATEGY": "merge(var.default_tags, var.tags)",
        "STANDARD_VARIABLES": "- prefix\n- region",
        "TARGET": "copilot",
        "ORG": "acme",
    }
    ctx = build_context(answers)

    assert ctx["PROVIDER_NAME"] == "aws"
    assert "aws" in ctx["PROVIDER_BLOCK"]
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terraform"


def test_build_context_gcp_defaults():
    answers = {
        "COMPANY_NAME": "GCPCo",
        "CLOUD_PROVIDER": "GCP",
        "MODULE_PREFIX": "tf-gcp",
        "ORCHESTRATION_TOOL": "Terramate",
        "ORCHESTRATION_DIR": "stacks",
        "CI_CD_PLATFORM": "GitLab CI",
        "AUTH_PATTERN": "Workload Identity Federation",
        "STATE_BACKEND": "GCS",
        "NAMING_PATTERN": "{prefix}-{type}",
        "TAG_STRATEGY": "merge(var.default_labels, var.labels)",
        "STANDARD_VARIABLES": "- prefix\n- location",
        "TARGET": "claude",
        "ORG": "gcpco",
    }
    ctx = build_context(answers)

    assert ctx["PROVIDER_NAME"] == "google"
    assert "google" in ctx["PROVIDER_BLOCK"]
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terramate"


def test_build_context_no_orchestration():
    answers = {
        "COMPANY_NAME": "Test",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf",
        "ORCHESTRATION_TOOL": "None",
        "ORCHESTRATION_DIR": ".",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "",
        "STATE_BACKEND": "",
        "NAMING_PATTERN": "",
        "TAG_STRATEGY": "",
        "STANDARD_VARIABLES": "",
        "TARGET": "both",
        "ORG": "test",
    }
    ctx = build_context(answers)
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terraform"
    assert ctx["VALIDATE_COMMAND"] == "terraform validate"


# ---------------------------------------------------------------------------
# generate_files
# ---------------------------------------------------------------------------


def test_generate_files_dry_run(tmp_path):
    """In dry-run mode, no files should be written."""
    answers = {
        "COMPANY_NAME": "DryRunCo",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": "Terragrunt",
        "ORCHESTRATION_DIR": "infra",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "Managed Identity / OIDC",
        "STATE_BACKEND": "Azure Blob Storage",
        "NAMING_PATTERN": "{prefix}-{type}-{suffix}",
        "TAG_STRATEGY": "merge(var.env_default_tags, var.tags)",
        "STANDARD_VARIABLES": "- prefix",
        "TARGET": "both",
        "ORG": "dryrunco",
    }
    ctx = build_context(answers)
    results = generate_files(ctx, tmp_path, dry_run=True)

    # No files written
    assert list(tmp_path.rglob("*")) == []
    # But results are populated
    assert len(results) > 0


def test_generate_files_fails_when_template_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        generator_module,
        "_build_output_specs",
        lambda context, templates_dir: [
            OutputSpec("missing.tmpl", "generated.md", "copilot")
        ],
    )

    with pytest.raises(GenerationError, match="missing template"):
        generate_files({}, tmp_path / "output", target="copilot", templates_dir=tmp_path)

    assert not (tmp_path / "output").exists()


def test_generate_files_skips_existing_before_template_preflight(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    existing = output_dir / "generated.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("original")
    monkeypatch.setattr(
        generator_module,
        "_build_output_specs",
        lambda context, templates_dir: [
            OutputSpec("missing.tmpl", "generated.md", "copilot")
        ],
    )

    results = generate_files({}, output_dir, target="copilot", templates_dir=tmp_path)

    assert results[0].skipped
    assert existing.read_text() == "original"


def test_generate_files_fails_on_unresolved_placeholders_without_writing(
    tmp_path, monkeypatch
):
    template = tmp_path / "template.tmpl"
    template.write_text("Company: {{COMPANY_NAME}}")
    monkeypatch.setattr(
        generator_module,
        "_build_output_specs",
        lambda context, templates_dir: [
            OutputSpec("template.tmpl", "generated.md", "copilot")
        ],
    )

    with pytest.raises(GenerationError, match="COMPANY_NAME"):
        generate_files({}, tmp_path / "output", target="copilot", templates_dir=tmp_path)

    assert not (tmp_path / "output").exists()


def test_generate_files_preflight_failure_preserves_existing_output(
    tmp_path, monkeypatch
):
    template = tmp_path / "template.tmpl"
    template.write_text("Company: {{COMPANY_NAME}}")
    output_dir = tmp_path / "output"
    existing = output_dir / "existing.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("original")
    monkeypatch.setattr(
        generator_module,
        "_build_output_specs",
        lambda context, templates_dir: [
            OutputSpec("template.tmpl", "generated.md", "copilot"),
            OutputSpec("missing.tmpl", "another.md", "copilot"),
        ],
    )

    with pytest.raises(GenerationError):
        generate_files(
            {"COMPANY_NAME": "Acme"},
            output_dir,
            target="copilot",
            templates_dir=tmp_path,
        )

    assert existing.read_text() == "original"
    assert not (output_dir / "generated.md").exists()


def test_generate_files_writes_copilot(tmp_path):
    answers = {
        "COMPANY_NAME": "Contoso",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": "None",
        "ORCHESTRATION_DIR": ".",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "Managed Identity / OIDC",
        "STATE_BACKEND": "Azure Blob Storage",
        "NAMING_PATTERN": "{prefix}-{type}-{suffix}",
        "TAG_STRATEGY": "merge(var.env_default_tags, var.tags)",
        "STANDARD_VARIABLES": "- prefix",
        "TARGET": "copilot",
        "ORG": "contoso",
    }
    ctx = build_context(answers)
    results = generate_files(ctx, tmp_path, target="copilot")

    written = [r for r in results if not r.skipped]
    assert len(written) > 0

    copilot_instructions = tmp_path / ".github" / "copilot-instructions.md"
    assert copilot_instructions.exists()
    content = copilot_instructions.read_text()
    assert "Contoso" in content
    # No unreplaced placeholders for core fields
    assert "{{COMPANY_NAME}}" not in content
    assert "{{CLOUD_PROVIDER}}" not in content


def test_generate_files_writes_claude(tmp_path):
    answers = {
        "COMPANY_NAME": "ClaudeCo",
        "CLOUD_PROVIDER": "AWS",
        "MODULE_PREFIX": "terraform-aws",
        "ORCHESTRATION_TOOL": "None",
        "ORCHESTRATION_DIR": ".",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "IAM Roles via OIDC",
        "STATE_BACKEND": "S3",
        "NAMING_PATTERN": "{prefix}-{type}",
        "TAG_STRATEGY": "merge(var.default_tags, var.tags)",
        "STANDARD_VARIABLES": "- prefix",
        "TARGET": "claude",
        "ORG": "claudeco",
    }
    ctx = build_context(answers)
    results = generate_files(ctx, tmp_path, target="claude")

    written = [r for r in results if not r.skipped]
    assert len(written) > 0

    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert "ClaudeCo" in content
    assert "{{COMPANY_NAME}}" not in content


def test_generate_files_skips_existing(tmp_path):
    """Existing files should be skipped by default."""
    existing = tmp_path / ".github" / "copilot-instructions.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("# existing content")

    answers = {
        "COMPANY_NAME": "SkipTest",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf",
        "ORCHESTRATION_TOOL": "None",
        "ORCHESTRATION_DIR": ".",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "",
        "STATE_BACKEND": "",
        "NAMING_PATTERN": "",
        "TAG_STRATEGY": "",
        "STANDARD_VARIABLES": "",
        "TARGET": "copilot",
        "ORG": "skiptest",
    }
    ctx = build_context(answers)
    results = generate_files(ctx, tmp_path, target="copilot", skip_existing=True)

    # The existing file should be skipped
    skipped_paths = {r.output_path for r in results if r.skipped}
    assert existing in skipped_paths

    # Content should be unchanged
    assert existing.read_text() == "# existing content"


def test_generate_files_overwrite(tmp_path):
    """With skip_existing=False, existing files are overwritten."""
    existing = tmp_path / ".github" / "copilot-instructions.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("# old content")

    answers = {
        "COMPANY_NAME": "OverwriteTest",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf",
        "ORCHESTRATION_TOOL": "None",
        "ORCHESTRATION_DIR": ".",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "",
        "STATE_BACKEND": "",
        "NAMING_PATTERN": "",
        "TAG_STRATEGY": "",
        "STANDARD_VARIABLES": "",
        "TARGET": "copilot",
        "ORG": "overwrite",
    }
    ctx = build_context(answers)
    generate_files(ctx, tmp_path, target="copilot", skip_existing=False)

    new_content = existing.read_text()
    assert "old content" not in new_content
    assert "OverwriteTest" in new_content


def test_generate_files_preserves_existing_file_mode(tmp_path):
    existing = tmp_path / ".github" / "copilot-instructions.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("# old content")
    os.chmod(existing, 0o750)

    answers = {
        "COMPANY_NAME": "ModeTest",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf",
        "ORCHESTRATION_TOOL": "None",
        "ORCHESTRATION_DIR": ".",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "",
        "STATE_BACKEND": "",
        "NAMING_PATTERN": "",
        "TAG_STRATEGY": "",
        "STANDARD_VARIABLES": "",
        "TARGET": "copilot",
        "ORG": "mode",
    }
    generate_files(build_context(answers), tmp_path, target="copilot", skip_existing=False)

    assert stat.S_IMODE(existing.stat().st_mode) == 0o750


def test_generate_files_rolls_back_after_publish_failure(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "first.tmpl").write_text("new first")
    (templates_dir / "second.tmpl").write_text("new second")
    output_dir = tmp_path / "output"
    (output_dir / "first.md").parent.mkdir(parents=True)
    (output_dir / "first.md").write_text("old first")
    (output_dir / "second.md").write_text("old second")
    monkeypatch.setattr(
        generator_module,
        "_build_output_specs",
        lambda context, templates_dir: [
            OutputSpec("first.tmpl", "first.md", "copilot"),
            OutputSpec("second.tmpl", "second.md", "copilot"),
        ],
    )
    original_replace = Path.replace
    replace_calls = 0

    def fail_on_second_replace(path, target):
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 2:
            raise OSError("simulated publish failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_on_second_replace)

    with pytest.raises(GenerationError, match="stage or publish"):
        generate_files(
            {},
            output_dir,
            target="copilot",
            skip_existing=False,
            templates_dir=templates_dir,
        )

    assert (output_dir / "first.md").read_text() == "old first"
    assert (output_dir / "second.md").read_text() == "old second"
    assert replace_calls == 3


def test_generate_files_reports_rollback_failure(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "first.tmpl").write_text("new first")
    (templates_dir / "second.tmpl").write_text("new second")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "first.md").write_text("old first")
    (output_dir / "second.md").write_text("old second")
    monkeypatch.setattr(
        generator_module,
        "_build_output_specs",
        lambda context, templates_dir: [
            OutputSpec("first.tmpl", "first.md", "copilot"),
            OutputSpec("second.tmpl", "second.md", "copilot"),
        ],
    )
    original_replace = Path.replace
    replace_calls = 0

    def fail_during_publish_and_rollback(path, target):
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls in (2, 3):
            raise OSError("simulated replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_during_publish_and_rollback)

    with pytest.raises(GenerationError, match="Rollback errors") as exc_info:
        generate_files(
            {},
            output_dir,
            target="copilot",
            skip_existing=False,
            templates_dir=templates_dir,
        )

    staging_dir = Path(
        str(exc_info.value).split("Recoverable staging directory: ", 1)[1]
    )
    assert staging_dir.is_dir()


def test_generate_files_reports_invalid_utf8_template(tmp_path, monkeypatch):
    template = tmp_path / "invalid.tmpl"
    template.write_bytes(b"\xff")
    monkeypatch.setattr(
        generator_module,
        "_build_output_specs",
        lambda context, templates_dir: [
            OutputSpec("invalid.tmpl", "generated.md", "copilot")
        ],
    )

    with pytest.raises(GenerationError, match="unable to read template.*generated.md"):
        generate_files({}, tmp_path / "output", target="copilot", templates_dir=tmp_path)


def test_generate_files_with_orchestration_creates_extra_files(tmp_path):
    """With orchestration enabled, additional files should be generated."""
    answers = {
        "COMPANY_NAME": "OrchTest",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": "Terragrunt",
        "ORCHESTRATION_DIR": "infra",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "Managed Identity / OIDC",
        "STATE_BACKEND": "Azure Blob Storage",
        "NAMING_PATTERN": "{prefix}-{type}",
        "TAG_STRATEGY": "merge(var.env_default_tags, var.tags)",
        "STANDARD_VARIABLES": "- prefix",
        "TARGET": "both",
        "ORG": "orchtest",
    }
    ctx_no_orch = build_context({**answers, "ORCHESTRATION_TOOL": "None"})
    ctx_orch = build_context(answers)

    results_no_orch = generate_files(ctx_no_orch, tmp_path / "no_orch", target="both")
    results_orch = generate_files(ctx_orch, tmp_path / "orch", target="both")

    assert len(results_orch) > len(results_no_orch)


def test_get_templates_dir_returns_directory():
    tdir = get_templates_dir()
    assert tdir.is_dir()
    # Should contain at least the copilot templates
    assert (tdir / "copilot").is_dir() or (tdir / "copilot/copilot-instructions.md.tmpl").exists()


# ---------------------------------------------------------------------------
# _cloud_template — cloud-specific template resolution
# ---------------------------------------------------------------------------


def test_cloud_template_returns_base_for_azure():
    """Azure uses the base template path (no override directory)."""
    tdir = get_templates_dir()
    result = _cloud_template("copilot/copilot-instructions.md.tmpl", "azure", tdir)
    assert result == "copilot/copilot-instructions.md.tmpl"


def test_cloud_template_returns_override_for_aws():
    """AWS should pick the cloud-specific override when it exists."""
    tdir = get_templates_dir()
    base = "copilot/copilot-instructions.md.tmpl"
    result = _cloud_template(base, "aws", tdir)
    expected = "copilot/aws/copilot-instructions.md.tmpl"
    if (tdir / expected).exists():
        assert result == expected
    else:
        assert result == base


def test_cloud_template_falls_back_when_no_override(tmp_path):
    """When no cloud-specific file exists, returns the base path."""
    (tmp_path / "copilot").mkdir()
    (tmp_path / "copilot" / "base.tmpl").write_text("base")
    result = _cloud_template("copilot/base.tmpl", "aws", tmp_path)
    assert result == "copilot/base.tmpl"


# ---------------------------------------------------------------------------
# _build_output_specs — output path correctness
# ---------------------------------------------------------------------------


def test_build_output_specs_pulumi_uses_tool_specific_paths():
    """Pulumi orchestration should produce pulumi-specific output paths."""
    tdir = get_templates_dir()
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "ORCHESTRATION_TOOL": "Pulumi",
    })
    specs = _build_output_specs(ctx, tdir)
    output_paths = [s.output_rel for s in specs]
    assert ".github/agents/pulumi-stack-manager.agent.md" in output_paths
    assert ".claude/commands/create-pulumi-stack.md" in output_paths


def test_build_output_specs_terragrunt_uses_tool_specific_paths():
    """Terragrunt orchestration should produce terragrunt-specific output paths."""
    tdir = get_templates_dir()
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "ORCHESTRATION_TOOL": "Terragrunt",
    })
    specs = _build_output_specs(ctx, tdir)
    output_paths = [s.output_rel for s in specs]
    assert ".github/agents/terragrunt-stack-manager.agent.md" in output_paths
    assert ".claude/commands/create-terragrunt-stack.md" in output_paths


def test_build_output_specs_no_orchestration_omits_stack_files():
    """Without orchestration, no stack-manager or stack command files."""
    tdir = get_templates_dir()
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "ORCHESTRATION_TOOL": "None",
    })
    specs = _build_output_specs(ctx, tdir)
    output_paths = [s.output_rel for s in specs]
    assert not any("stack-manager" in p for p in output_paths)
    assert not any("create-" in p and "-stack" in p for p in output_paths)


# ---------------------------------------------------------------------------
# PR review agent / command (issue #55)
# ---------------------------------------------------------------------------


def _pr_review_answers(
    cloud="Azure", orch="Terragrunt", target="both", cicd="GitHub Actions"
):
    """A complete interview answer set, as generate_files requires."""
    return {
        "COMPANY_NAME": "Acme Corp",
        "CLOUD_PROVIDER": cloud,
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": orch,
        # Mirror run_interview: no orchestration means no orchestration dir.
        "ORCHESTRATION_DIR": "." if orch == "None" else "infrastructure-config",
        "CI_CD_PLATFORM": cicd,
        "AUTH_PATTERN": "Managed Identity / OIDC",
        "STATE_BACKEND": "Azure Blob Storage",
        "NAMING_PATTERN": "{prefix}-{type}-{suffix}",
        "TAG_STRATEGY": "merge(var.env_default_tags, var.tags)",
        "STANDARD_VARIABLES": "- prefix",
        "TARGET": target,
        "ORG": "acme",
    }


@pytest.mark.parametrize("cloud", ["Azure", "AWS", "GCP"])
@pytest.mark.parametrize("orch", ["None", "Terragrunt", "Terramate", "Pulumi"])
def test_pr_reviewer_is_generated_for_every_cloud_and_orchestration(cloud, orch):
    """The PR reviewer is convention-driven, so it ships in every combination."""
    tdir = get_templates_dir()
    ctx = build_context({"CLOUD_PROVIDER": cloud, "ORCHESTRATION_TOOL": orch})
    output_paths = [s.output_rel for s in _build_output_specs(ctx, tdir)]
    assert ".github/agents/terraform-pr-reviewer.agent.md" in output_paths
    assert ".claude/commands/review-terraform-pr.md" in output_paths


def test_pr_reviewer_outputs_are_split_by_target():
    """The agent belongs to the copilot target and the command to claude."""
    tdir = get_templates_dir()
    ctx = build_context({"CLOUD_PROVIDER": "Azure", "ORCHESTRATION_TOOL": "Terragrunt"})
    specs = {s.output_rel: s for s in _build_output_specs(ctx, tdir)}
    assert specs[".github/agents/terraform-pr-reviewer.agent.md"].target == "copilot"
    assert specs[".claude/commands/review-terraform-pr.md"].target == "claude"


@pytest.mark.parametrize("cloud", ["Azure", "AWS", "GCP"])
@pytest.mark.parametrize("orch", ["None", "Terragrunt", "Terramate", "Pulumi"])
def test_pr_reviewer_renders_without_placeholders_and_keeps_conventions(
    tmp_path, cloud, orch
):
    """Generated review guidance resolves fully and cites workspace conventions."""
    ctx = build_context(_pr_review_answers(cloud=cloud, orch=orch))
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    agent = (tmp_path / ".github/agents/terraform-pr-reviewer.agent.md").read_text()
    command = (tmp_path / ".claude/commands/review-terraform-pr.md").read_text()

    for text, name in ((agent, "agent"), (command, "command")):
        assert "{{" not in text, f"{name} has an unresolved placeholder"
        # The workspace's own conventions must appear, not generic advice.
        assert ctx["MODULE_PREFIX"] in text, f"{name} omits the module prefix"
        assert ctx["TAG_MERGE_PATTERN"] in text, f"{name} omits the tag merge pattern"
        assert ctx["PROVIDER_NAME"] in text, f"{name} omits the provider name"
        assert ctx["COMMON_VARS_FILE"] in text, f"{name} omits the common vars file"
        # All eight review categories from the issue are covered.
        for heading in (
            "Naming compliance",
            "Tag and label strategy",
            "Variable design",
            "Test coverage",
            "Security",
            "Module structure",
            "Orchestration compliance",
            "Pipeline standards",
        ):
            assert heading in text, f"{name} is missing the '{heading}' category"
        # Severity vocabulary the report format depends on.
        for severity in ("Blocking", "Should fix", "Consider", "Verified"):
            assert severity in text, f"{name} is missing the '{severity}' severity"


def test_pr_reviewer_agent_has_valid_frontmatter(tmp_path):
    """The Copilot agent needs frontmatter with a description to be discovered."""
    import yaml

    ctx = build_context(_pr_review_answers(orch="None"))
    generate_files(ctx, tmp_path, target="copilot", skip_existing=False)
    text = (tmp_path / ".github/agents/terraform-pr-reviewer.agent.md").read_text()

    assert text.startswith("---\n")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert isinstance(frontmatter, dict)
    assert frontmatter["description"].strip()
    assert "tools" in frontmatter


def test_pr_reviewer_command_is_omitted_for_the_copilot_target(tmp_path):
    """A copilot-only run must not write the Claude command, and vice versa."""
    ctx = build_context(_pr_review_answers(orch="None"))

    copilot_dir = tmp_path / "copilot"
    generate_files(ctx, copilot_dir, target="copilot", skip_existing=False)
    assert (copilot_dir / ".github/agents/terraform-pr-reviewer.agent.md").is_file()
    assert not (copilot_dir / ".claude/commands/review-terraform-pr.md").exists()

    claude_dir = tmp_path / "claude"
    generate_files(ctx, claude_dir, target="claude", skip_existing=False)
    assert (claude_dir / ".claude/commands/review-terraform-pr.md").is_file()
    assert not (claude_dir / ".github/agents/terraform-pr-reviewer.agent.md").exists()


@pytest.mark.parametrize(
    "orch, expected, forbidden",
    [
        # Without orchestration the review must not ask for concepts that do
        # not exist, and must not name an instructions file that is never
        # generated (issue #55 review).
        ("None", ["no orchestration layer"], ["mock_outputs", "_envcommon", "StackReference"]),
        ("Terragrunt", ["_envcommon/", "mock_outputs"], ["StackReference", "generate_hcl"]),
        ("Terramate", ["generate_hcl", "terraform_remote_state"], ["mock_outputs", "_envcommon"]),
        ("Pulumi", ["StackReference", "ComponentResource"], ["mock_outputs", "_envcommon"]),
    ],
)
def test_pr_reviewer_orchestration_section_matches_the_tool(tmp_path, orch, expected, forbidden):
    """Section 7 must describe the workspace's actual orchestration tool."""
    ctx = build_context(_pr_review_answers(orch=orch))
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        for needle in expected:
            assert needle in text, f"{rel} ({orch}) should mention {needle!r}"
        for needle in forbidden:
            assert needle not in text, (
                f"{rel} ({orch}) must not mention {needle!r} from another tool"
            )
        # The "in use: None" phrasing that read as a broken sentence is gone.
        assert "in use: None" not in text


def test_pr_reviewer_does_not_reference_a_missing_instructions_file(tmp_path):
    """Without orchestration there is no *-configs.instructions.md to read."""
    ctx = build_context(_pr_review_answers(orch="None"))
    generate_files(ctx, tmp_path, target="copilot", skip_existing=False)
    text = (tmp_path / ".github/agents/terraform-pr-reviewer.agent.md").read_text()
    assert "configs.instructions.md" not in text
    assert "no orchestration layer" in text


def test_pr_reviewer_keeps_multiline_values_out_of_bullets(tmp_path):
    """Multi-line context values must be fenced, not inlined into a list item.

    PROVIDER_VERSION_CONSTRAINTS and PIPELINE_CONVENTIONS are multi-line; if
    they are interpolated mid-bullet the markdown list breaks (issue #55 review).
    """
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        for line in text.splitlines():
            if line.startswith("- ") and line.rstrip().endswith("{"):
                raise AssertionError(f"{rel}: multi-line value inlined in bullet: {line!r}")
        # The provider block is fenced as HCL.
        assert "```hcl\nterraform {" in text
        # Pipeline conventions start their own block, not mid-sentence.
        assert "Conventions: -" not in text


def test_pr_reviewer_resolves_the_real_base_ref(tmp_path):
    """The diff base must come from the PR, not a hardcoded `origin/main`.

    A PR targeting a release branch would otherwise be reviewed against the
    wrong change set (issue #55 review).
    """
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        assert "origin/main...HEAD" not in text, f"{rel} hardcodes origin/main"
        assert "baseRefName" in text, f"{rel} does not resolve the PR base"
        assert "refs/remotes/origin/HEAD" in text, f"{rel} has no default-branch fallback"


def test_pr_review_command_honours_its_arguments(tmp_path):
    """The Claude command advertises $ARGUMENTS, so it must actually use them."""
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="claude", skip_existing=False)
    text = (tmp_path / ".claude/commands/review-terraform-pr.md").read_text()

    assert "$ARGUMENTS" in text
    # Each advertised invocation mode has a concrete resolution.
    assert "gh pr diff" in text, "a PR number argument has no resolution"
    assert '-- <path>' in text, "a path argument is never applied as a filter"
    assert "a base ref" in text, "a base ref argument has no resolution"


@pytest.mark.parametrize(
    "orch, expected",
    [
        ("Pulumi", ["Pulumi.yaml", "*.ts", "*.py"]),
        ("Terragrunt", ["*.tf", "*.hcl"]),
        ("Terramate", ["*.tm.hcl"]),
        ("None", ["*.tf", "*.tfvars"]),
    ],
)
def test_pr_reviewer_file_scope_covers_the_tools_own_sources(tmp_path, orch, expected):
    """A Pulumi workspace's review must not skip the Pulumi program files."""
    ctx = build_context(_pr_review_answers(orch=orch))
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        for needle in expected:
            assert needle in text, f"{rel} ({orch}) omits {needle!r} from the review scope"


def test_pr_reviewer_describes_optional_correctly(tmp_path):
    """`optional()` applies to object attributes, not to top-level variables.

    Advising otherwise makes the reviewer raise false findings, and contradicts
    references/iac-best-practices.md (issue #55 review).
    """
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        assert "Optional inputs use `optional()`" not in text
        assert "optional(type, default)" in text
        assert "object variable" in text


@pytest.mark.parametrize(
    "cicd, expected, forbidden",
    [
        # Atlantis applies via a PR comment with server-side credentials, so
        # demanding a protected-branch apply job produces false findings (#55).
        (
            "Atlantis",
            ["atlantis apply", "Atlantis server environment"],
            [
                "apply job requires an environment approval",
                "OIDC federation",
                # Generic bullets that PIPELINE_REVIEW_CHECKS replaces.
                "apply gated on a protected branch",
                "Identity-based authentication",
            ],
        ),
        ("GitHub Actions", ["OIDC federation", "protected branch"], ["atlantis apply"]),
        ("GitLab CI", ["when: manual", "id_tokens"], ["atlantis apply"]),
        ("Azure DevOps", ["workload identity service connection"], ["atlantis apply"]),
    ],
)
def test_pr_reviewer_pipeline_checks_match_the_platform(tmp_path, cicd, expected, forbidden):
    """Section 8 must not impose one platform's workflow on another."""
    ctx = build_context(_pr_review_answers(cicd=cicd))
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        for needle in expected:
            assert needle in text, f"{rel} ({cicd}) should mention {needle!r}"
        for needle in forbidden:
            assert needle not in text, (
                f"{rel} ({cicd}) must not impose {needle!r} from another platform"
            )


def test_pr_reviewer_reviews_the_patch_not_whole_files(tmp_path):
    """Findings must be tied to changed lines, or the reviewer blames the author
    for pre-existing problems on untouched lines (issue #55 review)."""
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        assert "Review the patch, not the whole file" in text
        assert "added, modified, or **deleted**" in text, (
            f"{rel} does not treat deletions as reviewable"
        )
        # The patch itself is fetched, not only a name-only list.
        assert 'git diff "$BASE"...HEAD' in text


def test_pr_review_command_fetches_the_pr_patch(tmp_path):
    """A PR-number invocation must read that PR's patch, not the local checkout."""
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="claude", skip_existing=False)
    text = (tmp_path / ".claude/commands/review-terraform-pr.md").read_text()
    assert "gh pr diff 123`" in text or "gh pr diff 123 " in text or "`gh pr diff 123`" in text
    assert "the local checkout may be a different branch" in text


def test_pr_reviewer_terraform_sections_are_scoped_to_terraform(tmp_path):
    """Terraform-only checks must not be applied to Pulumi program sources."""
    ctx = build_context(_pr_review_answers(orch="Pulumi"))
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        # Pulumi sources are in scope ...
        assert "*.ts" in text
        # ... but the Terraform-only categories say so explicitly.
        assert text.count("Applies to Terraform") >= 2, (
            f"{rel} does not scope the Terraform-only checklist sections"
        )


def test_pr_reviewer_command_safety_note_is_accurate(tmp_path):
    """`terraform fmt` neither initialises modules nor executes code."""
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        assert "Both commands initialise" not in text, f"{rel} still misstates fmt"
        assert "only reads and formats files" in text
        assert "untrusted fork" in text


def test_pr_reviewer_treats_deletions_as_reviewable(tmp_path):
    """A removed test, encryption setting, or approval gate is a regression.

    Scoping findings to added/modified lines only would let those through
    (issue #55 review).
    """
    ctx = build_context(_pr_review_answers())
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        assert "added, modified, or **deleted**" in text
        assert "base-side line" in text, f"{rel} does not say how to cite a deletion"
        # The earlier, narrower rule must be gone.
        assert "adds or modifies;" not in text


@pytest.mark.parametrize("cicd", ["Atlantis", "GitHub Actions", "GitLab CI", "Azure DevOps"])
def test_pr_reviewer_pipeline_section_has_no_generic_bullets(tmp_path, cicd):
    """Section 8 must rely only on the platform-specific checks."""
    ctx = build_context(_pr_review_answers(cicd=cicd))
    generate_files(ctx, tmp_path, target="both", skip_existing=False)

    for rel in (
        ".github/agents/terraform-pr-reviewer.agent.md",
        ".claude/commands/review-terraform-pr.md",
    ):
        text = (tmp_path / rel).read_text()
        for generic in (
            "Plan on every change; apply gated on a protected branch with approval",
            "Identity-based authentication; no credential variables",
            "Plan runs on every change; apply is gated on a protected branch and an approval",
        ):
            assert generic not in text, f"{rel} ({cicd}) still imposes {generic!r}"


def test_new_placeholders_are_documented_in_the_readme():
    """CONTRIBUTING requires every new placeholder to appear in the README."""
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    for placeholder in (
        "{{ORCHESTRATION_REVIEW_CHECKS}}",
        "{{ORCHESTRATION_INSTRUCTIONS_REF}}",
        "{{REVIEW_FILE_SCOPE}}",
        "{{PIPELINE_REVIEW_CHECKS}}",
    ):
        assert placeholder in readme, f"{placeholder} is not documented in README.md"
