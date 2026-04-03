"""Tests for bootstrap_iac.generator."""

import pytest
from pathlib import Path

from bootstrap_iac.generator import resolve_placeholders, generate_files, get_templates_dir
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
