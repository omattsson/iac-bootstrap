"""Tests for bootstrap_iac.discovery — workspace auto-detection heuristics."""

from pathlib import Path

import pytest

from bootstrap_iac.discovery import (
    DiscoveryResult,
    scan_workspace,
    _detect_cloud_provider,
    _detect_module_prefix,
    _detect_orchestration,
    _detect_ci_cd,
    _detect_org_from_git,
    _detect_state_backend,
    _detect_naming_pattern,
    _detect_auth_pattern,
    _detect_tag_strategy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Return a fresh temporary directory to use as a workspace."""
    return tmp_path


# ---------------------------------------------------------------------------
# Cloud provider detection
# ---------------------------------------------------------------------------


def test_detect_cloud_provider_azure(workspace: Path):
    (workspace / "main.tf").write_text('provider "azurerm" {\n  features {}\n}\n')
    assert _detect_cloud_provider(workspace) == "Azure"


def test_detect_cloud_provider_aws(workspace: Path):
    (workspace / "main.tf").write_text('provider "aws" {\n  region = "us-east-1"\n}\n')
    assert _detect_cloud_provider(workspace) == "AWS"


def test_detect_cloud_provider_gcp(workspace: Path):
    (workspace / "main.tf").write_text('provider "google" {\n  project = "x"\n}\n')
    assert _detect_cloud_provider(workspace) == "GCP"


def test_detect_cloud_provider_from_required_providers(workspace: Path):
    (workspace / "versions.tf").write_text(
        'terraform {\n  required_providers {\n    "aws" = {\n'
        '      source = "hashicorp/aws"\n    }\n  }\n}\n'
    )
    assert _detect_cloud_provider(workspace) == "AWS"


def test_detect_cloud_provider_none(workspace: Path):
    (workspace / "readme.md").write_text("no terraform here")
    assert _detect_cloud_provider(workspace) is None


def test_detect_cloud_provider_highest_count(workspace: Path):
    """When multiple providers exist, the one with the most matches wins."""
    (workspace / "a.tf").write_text('provider "azurerm" {}')
    (workspace / "b.tf").write_text('provider "azurerm" {}')
    (workspace / "c.tf").write_text('provider "aws" {}')
    assert _detect_cloud_provider(workspace) == "Azure"


# ---------------------------------------------------------------------------
# Module prefix detection
# ---------------------------------------------------------------------------


def test_detect_module_prefix_tf_module(workspace: Path):
    (workspace / "tf-module-keyvault").mkdir()
    (workspace / "tf-module-network").mkdir()
    assert _detect_module_prefix(workspace) == "tf-module"


def test_detect_module_prefix_terraform_aws(workspace: Path):
    (workspace / "terraform-aws-s3").mkdir()
    (workspace / "terraform-aws-lambda").mkdir()
    assert _detect_module_prefix(workspace) == "terraform-aws"


def test_detect_module_prefix_modules_fallback(workspace: Path):
    (workspace / "modules").mkdir()
    assert _detect_module_prefix(workspace) == "modules"


def test_detect_module_prefix_none(workspace: Path):
    (workspace / "src").mkdir()
    assert _detect_module_prefix(workspace) is None


# ---------------------------------------------------------------------------
# Orchestration detection
# ---------------------------------------------------------------------------


def test_detect_orchestration_terragrunt(workspace: Path):
    infra = workspace / "infrastructure-config" / "dev"
    infra.mkdir(parents=True)
    (infra / "terragrunt.hcl").write_text("# terragrunt")
    tool, orch_dir = _detect_orchestration(workspace)
    assert tool == "Terragrunt"
    assert orch_dir == "infrastructure-config"


def test_detect_orchestration_terramate(workspace: Path):
    stacks = workspace / "stacks"
    stacks.mkdir()
    (stacks / "terramate.tm.hcl").write_text("# terramate")
    tool, orch_dir = _detect_orchestration(workspace)
    assert tool == "Terramate"
    assert orch_dir == "stacks"


def test_detect_orchestration_none(workspace: Path):
    (workspace / "main.tf").write_text("# plain tf")
    tool, orch_dir = _detect_orchestration(workspace)
    assert tool is None
    assert orch_dir is None


# ---------------------------------------------------------------------------
# CI/CD detection
# ---------------------------------------------------------------------------


def test_detect_ci_cd_github_actions(workspace: Path):
    wf = workspace / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: CI")
    platform, pipe_dir = _detect_ci_cd(workspace)
    assert platform == "GitHub Actions"
    assert pipe_dir == ".github/workflows"


def test_detect_ci_cd_azure_devops(workspace: Path):
    (workspace / "azure-pipelines.yml").write_text("trigger: none")
    platform, pipe_dir = _detect_ci_cd(workspace)
    assert platform == "Azure DevOps"
    assert pipe_dir == "."


def test_detect_ci_cd_gitlab(workspace: Path):
    (workspace / ".gitlab-ci.yml").write_text("stages: [plan]")
    platform, pipe_dir = _detect_ci_cd(workspace)
    assert platform == "GitLab CI"
    assert pipe_dir == "."


def test_detect_ci_cd_none(workspace: Path):
    platform, pipe_dir = _detect_ci_cd(workspace)
    assert platform is None
    assert pipe_dir is None


# ---------------------------------------------------------------------------
# State backend detection
# ---------------------------------------------------------------------------


def test_detect_state_backend_s3(workspace: Path):
    (workspace / "backend.tf").write_text(
        'terraform {\n  backend "s3" {\n    bucket = "my-state"\n  }\n}\n'
    )
    assert _detect_state_backend(workspace) == "S3"


def test_detect_state_backend_azurerm(workspace: Path):
    (workspace / "backend.tf").write_text(
        'terraform {\n  backend "azurerm" {\n'
        '    resource_group_name = "rg"\n  }\n}\n'
    )
    assert _detect_state_backend(workspace) == "Azure Blob Storage"


def test_detect_state_backend_gcs(workspace: Path):
    (workspace / "backend.tf").write_text(
        'terraform {\n  backend "gcs" {\n    bucket = "my-state"\n  }\n}\n'
    )
    assert _detect_state_backend(workspace) == "GCS"


def test_detect_state_backend_remote(workspace: Path):
    (workspace / "backend.tf").write_text(
        'terraform {\n  backend "remote" {\n'
        '    organization = "my-org"\n  }\n}\n'
    )
    assert _detect_state_backend(workspace) == "Terraform Cloud"


def test_detect_state_backend_none(workspace: Path):
    (workspace / "main.tf").write_text('resource "null_resource" "x" {}')
    assert _detect_state_backend(workspace) is None


# ---------------------------------------------------------------------------
# Naming pattern detection
# ---------------------------------------------------------------------------


def test_detect_naming_pattern_prefix_abbrev_suffix(workspace: Path):
    (workspace / "main.tf").write_text(
        'resource "azurerm_key_vault" "default" {\n'
        '  name = "${var.prefix}-${local.resource_abbreviation}-${local.suffix}"\n'
        "}\n"
    )
    result = _detect_naming_pattern(workspace)
    assert result == "{prefix}-{resource_abbreviation}-{suffix}"


def test_detect_naming_pattern_prefix_name(workspace: Path):
    (workspace / "main.tf").write_text(
        'resource "aws_s3_bucket" "default" {\n'
        '  name = "${var.prefix}-${var.name}"\n'
        "}\n"
    )
    result = _detect_naming_pattern(workspace)
    assert result == "{prefix}-{name}"


def test_detect_naming_pattern_skips_test_files(workspace: Path):
    tests = workspace / "tests"
    tests.mkdir()
    (tests / "test_main.tf").write_text(
        'name = "${var.prefix}-test"\n'
    )
    # No non-test .tf files with name patterns
    (workspace / "main.tf").write_text('resource "null_resource" "x" {}')
    assert _detect_naming_pattern(workspace) is None


def test_detect_naming_pattern_none(workspace: Path):
    (workspace / "main.tf").write_text('resource "null_resource" "x" {}')
    assert _detect_naming_pattern(workspace) is None


# ---------------------------------------------------------------------------
# Auth pattern detection
# ---------------------------------------------------------------------------


def test_detect_auth_pattern_github_oidc_aws(workspace: Path):
    wf = workspace / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "deploy.yml").write_text(
        "permissions:\n"
        "  id-token: write\n"
        "steps:\n"
        "  - uses: aws-actions/configure-aws-credentials@v4\n"
    )
    assert _detect_auth_pattern(workspace) == "IAM Roles via OIDC"


def test_detect_auth_pattern_github_oidc_azure(workspace: Path):
    wf = workspace / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "deploy.yml").write_text(
        "permissions:\n"
        "  id-token: write\n"
        "steps:\n"
        "  - uses: azure/login@v2\n"
    )
    assert _detect_auth_pattern(workspace) == "Managed Identity / OIDC"


def test_detect_auth_pattern_github_oidc_gcp(workspace: Path):
    wf = workspace / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "deploy.yml").write_text(
        "permissions:\n"
        "  id-token: write\n"
        "steps:\n"
        "  - uses: google-github-actions/auth@v2\n"
    )
    assert _detect_auth_pattern(workspace) == "Workload Identity Federation"


def test_detect_auth_pattern_github_oidc_generic(workspace: Path):
    wf = workspace / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "deploy.yml").write_text("permissions:\n  id-token: write\n")
    assert _detect_auth_pattern(workspace) == "OIDC"


def test_detect_auth_pattern_azure_devops(workspace: Path):
    (workspace / "azure-pipelines.yml").write_text(
        "steps:\n  - task: AzureCLI@2\n    inputs:\n"
        "      azureSubscription: my-connection\n"
    )
    assert _detect_auth_pattern(workspace) == "Managed Identity / OIDC"


def test_detect_auth_pattern_gitlab_oidc(workspace: Path):
    (workspace / ".gitlab-ci.yml").write_text(
        "plan:\n  id_tokens:\n    GITLAB_OIDC_TOKEN:\n"
        "      aud: https://gitlab.com\n"
    )
    assert _detect_auth_pattern(workspace) == "OIDC"


def test_detect_auth_pattern_provider_use_oidc(workspace: Path):
    (workspace / "provider.tf").write_text(
        'provider "azurerm" {\n  use_oidc = true\n  features {}\n}\n'
    )
    assert _detect_auth_pattern(workspace) == "Managed Identity / OIDC"


def test_detect_auth_pattern_none(workspace: Path):
    (workspace / "main.tf").write_text('resource "null_resource" "x" {}')
    assert _detect_auth_pattern(workspace) is None


# ---------------------------------------------------------------------------
# Tag strategy detection
# ---------------------------------------------------------------------------


def test_detect_tag_strategy_azure(workspace: Path):
    (workspace / "locals.tf").write_text(
        "locals {\n  tags = merge(var.env_default_tags, var.tags)\n}\n"
    )
    assert _detect_tag_strategy(workspace) == "merge(var.env_default_tags, var.tags)"


def test_detect_tag_strategy_aws(workspace: Path):
    (workspace / "locals.tf").write_text(
        "locals {\n  tags = merge(var.default_tags, var.tags)\n}\n"
    )
    assert _detect_tag_strategy(workspace) == "merge(var.default_tags, var.tags)"


def test_detect_tag_strategy_gcp_labels(workspace: Path):
    (workspace / "locals.tf").write_text(
        "locals {\n  labels = merge(var.default_labels, var.labels)\n}\n"
    )
    assert _detect_tag_strategy(workspace) == "merge(var.default_labels, var.labels)"


def test_detect_tag_strategy_none(workspace: Path):
    (workspace / "main.tf").write_text('resource "null_resource" "x" {}')
    assert _detect_tag_strategy(workspace) is None


# ---------------------------------------------------------------------------
# Org name detection
# ---------------------------------------------------------------------------


def test_detect_org_from_git_https(workspace: Path):
    git_dir = workspace / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text(
        "[remote \"origin\"]\n"
        "\turl = https://github.com/acme-corp/infra.git\n"
    )
    assert _detect_org_from_git(workspace) == "acme-corp"


def test_detect_org_from_git_ssh(workspace: Path):
    git_dir = workspace / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text(
        "[remote \"origin\"]\n"
        "\turl = git@github.com:my-org/my-repo.git\n"
    )
    assert _detect_org_from_git(workspace) == "my-org"


def test_detect_org_from_git_none(workspace: Path):
    assert _detect_org_from_git(workspace) is None


# ---------------------------------------------------------------------------
# Full scan_workspace integration
# ---------------------------------------------------------------------------


def test_scan_workspace_empty(workspace: Path):
    result = scan_workspace(workspace)
    assert result.workspace_path == workspace
    assert result.cloud_provider is None
    assert result.module_prefix is None
    assert result.orchestration_tool is None
    assert result.ci_cd_platform is None
    assert result.state_backend is None
    assert result.naming_pattern is None
    assert result.auth_pattern is None
    assert result.tag_strategy is None


def test_scan_workspace_azure_terragrunt(workspace: Path):
    """Simulate an Azure + Terragrunt workspace."""
    # Cloud provider
    (workspace / "main.tf").write_text('provider "azurerm" {\n  features {}\n}\n')
    # Module prefix
    (workspace / "tf-module-keyvault").mkdir()
    # Orchestration
    infra = workspace / "infrastructure-config" / "dev"
    infra.mkdir(parents=True)
    (infra / "terragrunt.hcl").write_text("# tg")
    # State backend
    (workspace / "backend.tf").write_text(
        'terraform {\n  backend "azurerm" {\n    container_name = "tfstate"\n  }\n}\n'
    )
    # Tag strategy
    (workspace / "locals.tf").write_text(
        "locals {\n  tags = merge(var.env_default_tags, var.tags)\n}\n"
    )

    result = scan_workspace(workspace)
    assert result.cloud_provider == "Azure"
    assert result.module_prefix == "tf-module"
    assert result.orchestration_tool == "Terragrunt"
    assert result.orchestration_dir == "infrastructure-config"
    assert result.state_backend == "Azure Blob Storage"
    assert result.tag_strategy == "merge(var.env_default_tags, var.tags)"


def test_scan_workspace_detects_existing_customizations(workspace: Path):
    gh = workspace / ".github"
    gh.mkdir()
    (gh / "copilot-instructions.md").write_text("# copilot")
    (workspace / "CLAUDE.md").write_text("# claude")

    result = scan_workspace(workspace)
    assert result.has_copilot_instructions is True
    assert result.has_claude_md is True
    assert len(result.notes) == 2
