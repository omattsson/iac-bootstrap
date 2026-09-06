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

    with pytest.raises(GenerationError, match="Rollback errors"):
        generate_files(
            {},
            output_dir,
            target="copilot",
            skip_existing=False,
            templates_dir=templates_dir,
        )


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
