"""Tests for bootstrap_iac.discovery — workspace auto-detection."""

import textwrap

from bootstrap_iac.discovery import (
    _detect_ci_cd,
    _detect_cloud_provider,
    _detect_module_prefix,
    _detect_naming_pattern,
    _detect_orchestration,
    _detect_state_backend,
    scan_workspace,
)


# ---------------------------------------------------------------------------
# Cloud provider detection
# ---------------------------------------------------------------------------


def test_detect_azure_provider(tmp_path):
    (tmp_path / "main.tf").write_text('provider "azurerm" {\n  features {}\n}\n')
    assert _detect_cloud_provider(tmp_path) == "Azure"


def test_detect_aws_provider(tmp_path):
    (tmp_path / "main.tf").write_text('provider "aws" {\n  region = "us-east-1"\n}\n')
    assert _detect_cloud_provider(tmp_path) == "AWS"


def test_detect_gcp_provider(tmp_path):
    (tmp_path / "main.tf").write_text('provider "google" {\n  project = "my-proj"\n}\n')
    assert _detect_cloud_provider(tmp_path) == "GCP"


def test_detect_cloud_provider_none(tmp_path):
    (tmp_path / "main.tf").write_text("# empty\n")
    assert _detect_cloud_provider(tmp_path) is None


def test_detect_cloud_provider_ignores_dot_terraform(tmp_path):
    dot_tf = tmp_path / ".terraform" / "providers"
    dot_tf.mkdir(parents=True)
    (dot_tf / "lock.tf").write_text('provider "aws" {}\n')
    assert _detect_cloud_provider(tmp_path) is None


def test_detect_cloud_from_required_providers(tmp_path):
    (tmp_path / "versions.tf").write_text(textwrap.dedent("""\
        terraform {
          required_providers {
            "azurerm" = {
              source = "hashicorp/azurerm"
            }
          }
        }
    """))
    assert _detect_cloud_provider(tmp_path) == "Azure"


def test_detect_cloud_from_unquoted_required_providers(tmp_path):
    (tmp_path / "versions.tf").write_text(textwrap.dedent("""\
        terraform {
          required_providers {
            aws = {
              source  = "hashicorp/aws"
              version = "~> 5.0"
            }
          }
        }
    """))
    assert _detect_cloud_provider(tmp_path) == "AWS"


# ---------------------------------------------------------------------------
# Module prefix detection
# ---------------------------------------------------------------------------


def test_detect_tf_module_prefix(tmp_path):
    (tmp_path / "tf-module-network").mkdir()
    (tmp_path / "tf-module-storage").mkdir()
    assert _detect_module_prefix(tmp_path) == "tf-module"


def test_detect_terraform_cloud_prefix(tmp_path):
    (tmp_path / "terraform-aws-s3").mkdir()
    (tmp_path / "terraform-aws-vpc").mkdir()
    assert _detect_module_prefix(tmp_path) == "terraform-aws"


def test_detect_modules_dir_fallback(tmp_path):
    (tmp_path / "modules").mkdir()
    assert _detect_module_prefix(tmp_path) == "modules"


def test_detect_module_prefix_none(tmp_path):
    (tmp_path / "src").mkdir()
    assert _detect_module_prefix(tmp_path) is None


# ---------------------------------------------------------------------------
# Orchestration detection
# ---------------------------------------------------------------------------


def test_detect_terragrunt(tmp_path):
    cfg = tmp_path / "infrastructure-config" / "dev"
    cfg.mkdir(parents=True)
    (cfg / "terragrunt.hcl").write_text("# root\n")
    tool, orch_dir = _detect_orchestration(tmp_path)
    assert tool == "Terragrunt"
    assert orch_dir == "infrastructure-config"


def test_detect_terramate(tmp_path):
    stacks = tmp_path / "stacks" / "prod"
    stacks.mkdir(parents=True)
    (stacks / "terramate.tm.hcl").write_text("# stack\n")
    tool, orch_dir = _detect_orchestration(tmp_path)
    assert tool == "Terramate"
    assert orch_dir == "stacks"


def test_detect_pulumi(tmp_path):
    (tmp_path / "Pulumi.yaml").write_text("name: my-project\n")
    tool, orch_dir = _detect_orchestration(tmp_path)
    assert tool == "Pulumi"
    assert orch_dir == "."


def test_detect_orchestration_none(tmp_path):
    (tmp_path / "main.tf").write_text("# no orch\n")
    tool, orch_dir = _detect_orchestration(tmp_path)
    assert tool is None
    assert orch_dir is None


# ---------------------------------------------------------------------------
# CI/CD detection
# ---------------------------------------------------------------------------


def test_detect_github_actions(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("on: push\n")
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform == "GitHub Actions"
    assert pipeline_dir == ".github/workflows"


def test_detect_azure_devops(tmp_path):
    (tmp_path / "azure-pipelines.yml").write_text("trigger:\n  - main\n")
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform == "Azure DevOps"
    assert pipeline_dir == "."


def test_detect_gitlab_ci(tmp_path):
    (tmp_path / ".gitlab-ci.yml").write_text("stages:\n  - build\n")
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform == "GitLab CI"
    assert pipeline_dir == "."


def test_detect_ci_cd_none(tmp_path):
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform is None
    assert pipeline_dir is None


# ---------------------------------------------------------------------------
# State backend detection
# ---------------------------------------------------------------------------


def test_detect_azurerm_backend(tmp_path):
    (tmp_path / "backend.tf").write_text(textwrap.dedent("""\
        terraform {
          backend "azurerm" {
            resource_group_name  = "rg-state"
            storage_account_name = "ststate"
            container_name       = "tfstate"
          }
        }
    """))
    assert _detect_state_backend(tmp_path) == "Azure Blob Storage"


def test_detect_s3_backend(tmp_path):
    (tmp_path / "backend.tf").write_text(textwrap.dedent("""\
        terraform {
          backend "s3" {
            bucket = "my-state-bucket"
            key    = "terraform.tfstate"
            region = "us-east-1"
          }
        }
    """))
    assert _detect_state_backend(tmp_path) == "S3"


def test_detect_gcs_backend(tmp_path):
    (tmp_path / "backend.tf").write_text(textwrap.dedent("""\
        terraform {
          backend "gcs" {
            bucket = "my-state-bucket"
          }
        }
    """))
    assert _detect_state_backend(tmp_path) == "GCS"


def test_detect_terraform_cloud_backend(tmp_path):
    (tmp_path / "backend.tf").write_text(textwrap.dedent("""\
        terraform {
          cloud {
            organization = "my-org"
          }
        }
    """))
    assert _detect_state_backend(tmp_path) == "Terraform Cloud"


def test_detect_state_backend_none(tmp_path):
    (tmp_path / "main.tf").write_text("resource \"null_resource\" \"x\" {}\n")
    assert _detect_state_backend(tmp_path) is None


def test_detect_state_backend_ignores_dot_terraform(tmp_path):
    dot_tf = tmp_path / ".terraform" / "providers"
    dot_tf.mkdir(parents=True)
    (dot_tf / "backend.tf").write_text('backend "s3" {}\n')
    assert _detect_state_backend(tmp_path) is None


# ---------------------------------------------------------------------------
# Naming pattern detection
# ---------------------------------------------------------------------------


def test_detect_naming_pattern_prefix_style(tmp_path):
    (tmp_path / "locals.tf").write_text(textwrap.dedent("""\
        locals {
          name = "${var.prefix}-rg-${var.suffix}"
        }
    """))
    assert _detect_naming_pattern(tmp_path) is not None
    assert "prefix" in _detect_naming_pattern(tmp_path)


def test_detect_naming_pattern_format_style(tmp_path):
    (tmp_path / "locals.tf").write_text(textwrap.dedent("""\
        locals {
          name = format("%s-rg-%s", var.prefix, var.suffix)
        }
    """))
    assert _detect_naming_pattern(tmp_path) is not None


def test_detect_naming_pattern_none(tmp_path):
    (tmp_path / "main.tf").write_text("resource \"null_resource\" \"x\" {}\n")
    assert _detect_naming_pattern(tmp_path) is None


# ---------------------------------------------------------------------------
# scan_workspace integration
# ---------------------------------------------------------------------------


def test_scan_workspace_full(tmp_path):
    """Integration test: scan a workspace with multiple signals."""
    # Create provider file
    (tmp_path / "main.tf").write_text('provider "azurerm" {\n  features {}\n}\n')

    # Create backend
    (tmp_path / "backend.tf").write_text(textwrap.dedent("""\
        terraform {
          backend "azurerm" {
            resource_group_name = "rg-state"
          }
        }
    """))

    # Create module dirs
    (tmp_path / "tf-module-network").mkdir()

    # Create orchestration
    cfg = tmp_path / "infrastructure-config" / "dev"
    cfg.mkdir(parents=True)
    (cfg / "terragrunt.hcl").write_text("# root\n")

    # Create CI
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("on: push\n")

    # Create naming pattern
    (tmp_path / "locals.tf").write_text(textwrap.dedent("""\
        locals {
          name = "${var.prefix}-rg-${var.suffix}"
        }
    """))

    result = scan_workspace(tmp_path)

    assert result.cloud_provider == "Azure"
    assert result.module_prefix == "tf-module"
    assert result.orchestration_tool == "Terragrunt"
    assert result.orchestration_dir == "infrastructure-config"
    assert result.ci_cd_platform == "GitHub Actions"
    assert result.pipeline_dir == ".github/workflows"
    assert result.state_backend == "Azure Blob Storage"
    assert result.naming_pattern is not None
    assert "prefix" in result.naming_pattern


def test_scan_workspace_empty(tmp_path):
    """Graceful degradation: empty workspace returns None for all detections."""
    result = scan_workspace(tmp_path)

    assert result.cloud_provider is None
    assert result.module_prefix is None
    assert result.orchestration_tool is None
    assert result.orchestration_dir is None
    assert result.ci_cd_platform is None
    assert result.pipeline_dir is None
    assert result.state_backend is None
    assert result.naming_pattern is None
    assert result.notes == []


def test_scan_workspace_detects_existing_copilot_instructions(tmp_path):
    gh = tmp_path / ".github"
    gh.mkdir()
    (gh / "copilot-instructions.md").write_text("# Copilot instructions\n")
    result = scan_workspace(tmp_path)
    assert result.has_copilot_instructions is True
    assert any("copilot-instructions.md" in n for n in result.notes)


def test_scan_workspace_detects_existing_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Claude\n")
    result = scan_workspace(tmp_path)
    assert result.has_claude_md is True
    assert any("CLAUDE.md" in n for n in result.notes)
