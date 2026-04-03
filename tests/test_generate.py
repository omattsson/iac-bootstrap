"""Tests for bootstrap_iac.generate — template rendering and file generation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from bootstrap_iac.generate import (
    _build_test_standard_variables,
    _build_tag_strategy,
    build_placeholders,
    find_templates_dir,
    generate_files,
    render_template,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_answers(**overrides) -> dict:
    """Return a minimal set of interview answers suitable for testing."""
    base = {
        "company_name": "TestCorp",
        "cloud_provider": "Azure",
        "module_prefix": "tf-module",
        "module_source_pattern": "git::https://github.com/testcorp/tf-module-{name}?ref={tag}",
        "orchestration_tool": "Terragrunt",
        "orchestration_dir": "infrastructure-config",
        "cicd_platform": "GitHub Actions",
        "auth_pattern": "# OIDC auth",
        "auth_requirements": "- Set up OIDC",
        "naming_pattern": "`{prefix}-{type}-{suffix}`",
        "tag_merge": "merge(var.env_default_tags, var.tags)",
        "tag_required": "environment, product",
        "standard_variables": (
            "- `prefix` — Resource name prefix\n"
            "- `location` — Azure region\n"
            "- `resource_group_name` — Target RG"
        ),
        "version_tag_location": "`subscription.hcl` → `module_tags` local",
        "target_tools": "both",
        "pipeline_dir": ".github/workflows",
        "org": "testcorp",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# find_templates_dir
# ---------------------------------------------------------------------------

class TestFindTemplatesDir:
    def test_finds_references_dir_in_repo(self):
        # The repo has a references/ directory relative to the package location
        templates = find_templates_dir()
        assert templates.exists()
        assert (templates / "copilot" / "copilot-instructions.md.tmpl").exists()

    def test_returns_path_object(self):
        templates = find_templates_dir()
        assert isinstance(templates, Path)


# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------

class TestRenderTemplate:
    def test_replaces_single_placeholder(self, tmp_path):
        tmpl = tmp_path / "test.tmpl"
        tmpl.write_text("Hello {{COMPANY_NAME}}!")
        result = render_template(tmpl, {"COMPANY_NAME": "Acme"})
        assert result == "Hello Acme!"

    def test_replaces_multiple_placeholders(self, tmp_path):
        tmpl = tmp_path / "test.tmpl"
        tmpl.write_text("{{COMPANY_NAME}} uses {{CLOUD_PROVIDER}}.")
        result = render_template(tmpl, {"COMPANY_NAME": "Acme", "CLOUD_PROVIDER": "Azure"})
        assert result == "Acme uses Azure."

    def test_unknown_placeholder_left_as_todo(self, tmp_path):
        tmpl = tmp_path / "test.tmpl"
        tmpl.write_text("Value: {{UNKNOWN_KEY}}")
        result = render_template(tmpl, {})
        # Unknown placeholders are not touched (no replacement dict entry)
        assert "{{UNKNOWN_KEY}}" in result

    def test_empty_value_uses_todo_comment(self, tmp_path):
        tmpl = tmp_path / "test.tmpl"
        tmpl.write_text("Value: {{EMPTY_KEY}}")
        result = render_template(tmpl, {"EMPTY_KEY": ""})
        assert "# TODO: set EMPTY_KEY" in result

    def test_does_not_double_replace(self, tmp_path):
        tmpl = tmp_path / "test.tmpl"
        tmpl.write_text("{{A}} and {{B}}")
        result = render_template(tmpl, {"A": "alpha", "B": "beta"})
        assert result == "alpha and beta"


# ---------------------------------------------------------------------------
# _build_test_standard_variables
# ---------------------------------------------------------------------------

class TestBuildTestStandardVariables:
    def test_basic_conversion(self):
        std_vars = (
            "- `prefix` — Resource name prefix\n"
            "- `location` — Azure region\n"
            "- `tags` — Additional tags"
        )
        result = _build_test_standard_variables(std_vars)
        assert 'prefix = "mock-prefix"' in result
        assert 'location = "mock-location"' in result
        assert 'tags = "mock-tags"' in result
        assert result.startswith("variables {")
        assert result.endswith("}")

    def test_empty_input(self):
        result = _build_test_standard_variables("")
        assert "variables {" in result

    def test_handles_missing_description(self):
        std_vars = "- `region`\n- `prefix`"
        result = _build_test_standard_variables(std_vars)
        assert 'region = "mock-region"' in result
        assert 'prefix = "mock-prefix"' in result


# ---------------------------------------------------------------------------
# _build_tag_strategy
# ---------------------------------------------------------------------------

class TestBuildTagStrategy:
    def test_azure_tag_strategy(self):
        result = _build_tag_strategy(
            "Azure", "merge(var.env_default_tags, var.tags)", "environment, product"
        )
        assert "merge(var.env_default_tags, var.tags)" in result
        assert "environment, product" in result

    def test_gcp_uses_labels(self):
        result = _build_tag_strategy(
            "GCP", "merge(var.labels, var.extra_labels)", "environment, product"
        )
        assert "labels" in result


# ---------------------------------------------------------------------------
# build_placeholders
# ---------------------------------------------------------------------------

class TestBuildPlaceholders:
    def test_all_core_keys_present(self):
        answers = _make_answers()
        placeholders = build_placeholders(answers)
        required_keys = [
            "COMPANY_NAME", "CLOUD_PROVIDER", "MODULE_PREFIX",
            "ORCHESTRATION_TOOL", "CI_CD_PLATFORM", "PROVIDER_NAME",
            "STANDARD_VARIABLES", "NAMING_PATTERN", "TAG_MERGE_PATTERN",
            "PIPELINE_DIR", "ORCHESTRATION_DIR", "AUTH_PATTERN",
            "VALIDATE_COMMAND", "PLAN_COMMAND", "PLAN_ALL_COMMAND",
        ]
        for key in required_keys:
            assert key in placeholders, f"Missing placeholder: {key}"

    def test_azure_provider_name(self):
        answers = _make_answers(cloud_provider="Azure")
        placeholders = build_placeholders(answers)
        assert placeholders["PROVIDER_NAME"] == "azurerm"

    def test_aws_provider_name(self):
        answers = _make_answers(cloud_provider="AWS")
        placeholders = build_placeholders(answers)
        assert placeholders["PROVIDER_NAME"] == "aws"

    def test_gcp_provider_name(self):
        answers = _make_answers(cloud_provider="GCP")
        placeholders = build_placeholders(answers)
        assert placeholders["PROVIDER_NAME"] == "google"

    def test_terragrunt_commands(self):
        answers = _make_answers(orchestration_tool="Terragrunt")
        placeholders = build_placeholders(answers)
        assert "terragrunt" in placeholders["PLAN_COMMAND"]
        assert "terragrunt" in placeholders["VALIDATE_COMMAND"]

    def test_terramate_commands(self):
        answers = _make_answers(orchestration_tool="Terramate")
        placeholders = build_placeholders(answers)
        assert "terramate" in placeholders["PLAN_COMMAND"].lower()

    def test_no_orchestration_uses_terraform(self):
        answers = _make_answers(orchestration_tool="None")
        placeholders = build_placeholders(answers)
        assert "terraform" in placeholders["PLAN_COMMAND"]

    def test_company_name_propagated(self):
        answers = _make_answers(company_name="WidgetCo")
        placeholders = build_placeholders(answers)
        assert placeholders["COMPANY_NAME"] == "WidgetCo"

    def test_module_source_pattern_wrapped(self):
        answers = _make_answers(module_source_pattern="git::https://example.com/repo")
        placeholders = build_placeholders(answers)
        assert "git::https://example.com/repo" in placeholders["MODULE_SOURCE_PATTERN"]


# ---------------------------------------------------------------------------
# generate_files
# ---------------------------------------------------------------------------

class TestGenerateFiles:
    def test_generates_copilot_files(self, tmp_path):
        answers = _make_answers(target_tools="copilot")
        written, skipped = generate_files(answers, tmp_path)
        # copilot-instructions.md must be generated
        assert (tmp_path / ".github" / "copilot-instructions.md").exists()
        assert len(written) > 0

    def test_generates_claude_files(self, tmp_path):
        answers = _make_answers(target_tools="claude")
        written, skipped = generate_files(answers, tmp_path)
        assert (tmp_path / "CLAUDE.md").exists()

    def test_generates_both_tools(self, tmp_path):
        answers = _make_answers(target_tools="both")
        written, skipped = generate_files(answers, tmp_path)
        assert (tmp_path / ".github" / "copilot-instructions.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_orchestration_files_generated_when_tool_set(self, tmp_path):
        answers = _make_answers(orchestration_tool="Terragrunt", target_tools="copilot")
        written, skipped = generate_files(answers, tmp_path)
        agents_dir = tmp_path / ".github" / "agents"
        agent_files = list(agents_dir.glob("*stack-manager*"))
        assert len(agent_files) > 0

    def test_no_orchestration_files_when_none(self, tmp_path):
        answers = _make_answers(orchestration_tool="None", target_tools="copilot")
        written, skipped = generate_files(answers, tmp_path)
        agents_dir = tmp_path / ".github" / "agents"
        agent_files = list(agents_dir.glob("*stack-manager*")) if agents_dir.exists() else []
        assert len(agent_files) == 0

    def test_skips_existing_files_by_default(self, tmp_path):
        answers = _make_answers(target_tools="claude")
        # Pre-create the output file
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_text("existing content")

        written, skipped = generate_files(answers, tmp_path, overwrite=False)
        assert claude_md in skipped
        assert claude_md.read_text() == "existing content"

    def test_overwrite_flag_replaces_existing(self, tmp_path):
        answers = _make_answers(target_tools="claude")
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("old content")

        written, skipped = generate_files(answers, tmp_path, overwrite=True)
        assert claude_md in written
        assert "old content" not in claude_md.read_text()

    def test_placeholders_replaced_in_output(self, tmp_path):
        answers = _make_answers(company_name="TestCorp", target_tools="copilot")
        generate_files(answers, tmp_path)
        instructions = (tmp_path / ".github" / "copilot-instructions.md").read_text()
        assert "TestCorp" in instructions
        assert "{{COMPANY_NAME}}" not in instructions

    def test_creates_output_subdirs(self, tmp_path):
        answers = _make_answers(target_tools="copilot")
        generate_files(answers, tmp_path)
        assert (tmp_path / ".github" / "agents").is_dir()
        assert (tmp_path / ".github" / "skills").is_dir()
        assert (tmp_path / ".github" / "instructions").is_dir()
