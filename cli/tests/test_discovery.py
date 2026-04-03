"""Tests for bootstrap_iac.discovery."""

from pathlib import Path

import pytest

from bootstrap_iac.discovery import DiscoveryResult, scan_workspace


# ---------------------------------------------------------------------------
# scan_workspace — cloud provider detection
# ---------------------------------------------------------------------------


def test_detect_azure_from_provider_block(tmp_path):
    (tmp_path / "main.tf").write_text('provider "azurerm" {\n  features {}\n}')
    result = scan_workspace(tmp_path)
    assert result.cloud_provider == "Azure"


def test_detect_aws_from_provider_block(tmp_path):
    (tmp_path / "main.tf").write_text('provider "aws" {\n  region = "us-east-1"\n}')
    result = scan_workspace(tmp_path)
    assert result.cloud_provider == "AWS"


def test_detect_gcp_from_provider_block(tmp_path):
    (tmp_path / "main.tf").write_text('provider "google" {\n  project = "my-project"\n}')
    result = scan_workspace(tmp_path)
    assert result.cloud_provider == "GCP"


def test_detect_cloud_from_required_providers(tmp_path):
    (tmp_path / "versions.tf").write_text(
        'terraform {\n  required_providers {\n    "aws" = {\n      source = "hashicorp/aws"\n    }\n  }\n}'
    )
    result = scan_workspace(tmp_path)
    assert result.cloud_provider == "AWS"


def test_no_tf_files_returns_none(tmp_path):
    result = scan_workspace(tmp_path)
    assert result.cloud_provider is None


# ---------------------------------------------------------------------------
# scan_workspace — orchestration detection
# ---------------------------------------------------------------------------


def test_detect_terragrunt(tmp_path):
    infra = tmp_path / "infrastructure-config" / "dev" / "platform" / "networking"
    infra.mkdir(parents=True)
    (infra / "terragrunt.hcl").write_text('include "root" {}')
    result = scan_workspace(tmp_path)
    assert result.orchestration_tool == "Terragrunt"
    assert result.orchestration_dir == "infrastructure-config"


def test_detect_terramate(tmp_path):
    stacks = tmp_path / "stacks" / "dev"
    stacks.mkdir(parents=True)
    (stacks / "terramate.tm.hcl").write_text("stack {}")
    result = scan_workspace(tmp_path)
    assert result.orchestration_tool == "Terramate"
    assert result.orchestration_dir == "stacks"


def test_no_orchestration(tmp_path):
    (tmp_path / "main.tf").write_text("# plain terraform")
    result = scan_workspace(tmp_path)
    assert result.orchestration_tool is None
    assert result.orchestration_dir is None


# ---------------------------------------------------------------------------
# scan_workspace — CI/CD detection
# ---------------------------------------------------------------------------


def test_detect_github_actions(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("on: push")
    result = scan_workspace(tmp_path)
    assert result.ci_cd_platform == "GitHub Actions"
    assert result.pipeline_dir == ".github/workflows"


def test_detect_azure_devops(tmp_path):
    (tmp_path / "azure-pipelines.yml").write_text("trigger:\n- main")
    result = scan_workspace(tmp_path)
    assert result.ci_cd_platform == "Azure DevOps"


def test_detect_gitlab_ci(tmp_path):
    (tmp_path / ".gitlab-ci.yml").write_text("stages:\n- plan")
    result = scan_workspace(tmp_path)
    assert result.ci_cd_platform == "GitLab CI"


def test_no_ci_cd(tmp_path):
    result = scan_workspace(tmp_path)
    assert result.ci_cd_platform is None


# ---------------------------------------------------------------------------
# scan_workspace — module prefix detection
# ---------------------------------------------------------------------------


def test_detect_module_prefix(tmp_path):
    (tmp_path / "tf-module-keyvault").mkdir()
    (tmp_path / "tf-module-networking").mkdir()
    result = scan_workspace(tmp_path)
    assert result.module_prefix == "tf-module"


def test_detect_terraform_aws_prefix(tmp_path):
    (tmp_path / "terraform-aws-s3").mkdir()
    (tmp_path / "terraform-aws-vpc").mkdir()
    result = scan_workspace(tmp_path)
    assert result.module_prefix == "terraform-aws"


def test_detect_modules_directory(tmp_path):
    (tmp_path / "modules").mkdir()
    result = scan_workspace(tmp_path)
    assert result.module_prefix == "modules"


def test_no_module_prefix(tmp_path):
    (tmp_path / "some-random-dir").mkdir()
    result = scan_workspace(tmp_path)
    assert result.module_prefix is None


# ---------------------------------------------------------------------------
# scan_workspace — existing customisation detection
# ---------------------------------------------------------------------------


def test_detect_existing_copilot_instructions(tmp_path):
    gh = tmp_path / ".github"
    gh.mkdir()
    (gh / "copilot-instructions.md").write_text("# existing")
    result = scan_workspace(tmp_path)
    assert result.has_copilot_instructions is True
    assert any("copilot-instructions" in n for n in result.notes)


def test_detect_existing_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# existing")
    result = scan_workspace(tmp_path)
    assert result.has_claude_md is True
    assert any("CLAUDE.md" in n for n in result.notes)


def test_empty_workspace_returns_defaults(tmp_path):
    result = scan_workspace(tmp_path)
    assert result.workspace_path == tmp_path
    assert result.cloud_provider is None
    assert result.module_prefix is None
    assert result.orchestration_tool is None
    assert result.ci_cd_platform is None
    assert result.has_copilot_instructions is False
    assert result.has_claude_md is False
    assert result.notes == []
