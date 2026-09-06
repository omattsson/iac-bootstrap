"""Tests for bootstrap_iac.interview — build_context."""

import pytest

from bootstrap_iac.interview import build_context


# ---------------------------------------------------------------------------
# build_context — cloud-specific defaults
# ---------------------------------------------------------------------------


def test_build_context_azure_defaults():
    ctx = build_context({"CLOUD_PROVIDER": "Azure", "COMPANY_NAME": "TestCo"})
    assert ctx["COMPANY_SLUG"] == "testco"
    assert ctx["COMPANY_SLUG_UPPER"] == "TESTCO"
    assert ctx["PROVIDER_NAME"] == "azurerm"
    assert ctx["TAG_ATTRIBUTE"] == "tags"
    assert "azurerm" in ctx["PROVIDER_BLOCK"]
    assert ctx["PROVIDER_RESOURCE"] == "azurerm_resource_group"
    assert "." not in ctx["PROVIDER_RESOURCE"]
    assert "env_default_tags" in ctx["STANDARD_VARIABLES"]
    assert "env_default_tags" in ctx["TAG_STRATEGY"]
    assert "env_default_tags" in ctx["TAG_MERGE_PATTERN"]
    assert "env_default_tags" in ctx["TAG_MERGE_LOCAL"]


def test_build_context_company_slug_sanitizes_names():
    ctx = build_context({"CLOUD_PROVIDER": "Azure", "COMPANY_NAME": "Acme & Co."})
    assert ctx["COMPANY_SLUG"] == "acme-co"
    assert ctx["COMPANY_SLUG_UPPER"] == "ACME_CO"


def test_build_context_aws_defaults():
    ctx = build_context({"CLOUD_PROVIDER": "AWS", "COMPANY_NAME": "TestCo"})
    assert ctx["PROVIDER_NAME"] == "aws"
    assert ctx["NAME_ATTRIBUTE"] == "name"
    assert ctx["NAMING_ATTRIBUTE"] == "name = local.name"
    assert ctx["AWS_ACCOUNT_ID"] == "123456789012"
    assert ctx["AWS_DEFAULT_REGION"] == "us-east-1"
    assert ctx["TERRAFORM_ROLE_NAME"] == "TerraformDeployRole"
    assert ctx["STATE_BUCKET"] == "terraform-state-example"
    assert ctx["STATE_BUCKET_REGION"] == "us-east-1"
    assert ctx["STATE_KEY_PREFIX"] == "terraform/"
    assert ctx["LOCK_TABLE"] == "terraform-state-locks"
    assert ctx["TAG_ATTRIBUTE"] == "tags"
    assert "aws" in ctx["PROVIDER_BLOCK"]
    assert ctx["PROVIDER_RESOURCE"] == "aws_s3_bucket"
    assert "." not in ctx["PROVIDER_RESOURCE"]
    assert "env_default_tags" in ctx["STANDARD_VARIABLES"]
    assert "env_default_tags" in ctx["TAG_STRATEGY"]
    assert "env_default_tags" in ctx["TAG_MERGE_PATTERN"]
    assert "env_default_tags" in ctx["TAG_MERGE_LOCAL"]


def test_build_context_gcp_defaults():
    ctx = build_context({"CLOUD_PROVIDER": "GCP", "COMPANY_NAME": "TestCo"})
    assert ctx["PROVIDER_NAME"] == "google"
    assert ctx["TAG_ATTRIBUTE"] == "labels"
    assert "google" in ctx["PROVIDER_BLOCK"]
    assert ctx["PROVIDER_RESOURCE"] == "google_storage_bucket"
    assert ctx["GCP_PROJECT_ID"] == "test-project-123"
    assert ctx["GCP_PROJECT_NUMBER"] == "123456789"
    assert ctx["WIF_POOL"] == "terraform-pool"
    assert ctx["WIF_PROVIDER"] == "github-provider"
    assert "." not in ctx["PROVIDER_RESOURCE"]
    assert "env_default_labels" in ctx["STANDARD_VARIABLES"]
    assert "env_default_labels" in ctx["TAG_STRATEGY"]
    assert "env_default_labels" in ctx["TAG_MERGE_PATTERN"]
    assert "env_default_labels" in ctx["TAG_MERGE_LOCAL"]


# ---------------------------------------------------------------------------
# build_context — orchestration defaults
# ---------------------------------------------------------------------------


def test_build_context_terragrunt_defaults():
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "ORCHESTRATION_TOOL": "Terragrunt",
    })
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terragrunt"
    assert "terragrunt" in ctx["VALIDATE_COMMAND"]


def test_build_context_terramate_defaults():
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "ORCHESTRATION_TOOL": "Terramate",
    })
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terramate"
    assert "terramate" in ctx["VALIDATE_COMMAND"]


def test_build_context_no_orchestration():
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "ORCHESTRATION_TOOL": "None",
    })
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terraform"


def test_build_context_pulumi_defaults():
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "ORCHESTRATION_TOOL": "Pulumi",
    })
    assert ctx["ORCHESTRATION_TOOL_LOWER"] == "pulumi"
    assert "pulumi preview" in ctx["VALIDATE_COMMAND"]
    assert "pulumi preview" in ctx["PLAN_COMMAND"]
    assert "{stack}" in ctx["PLAN_SINGLE_COMMAND"]
    assert "Pulumi.yaml" in ctx["HIERARCHY_DIAGRAM"]
    # Pulumi-specific context keys
    assert ctx["PULUMI_NAMESPACE"] == "project"
    assert ctx["PULUMI_LANGUAGE"] == "Python"
    assert ctx["PULUMI_LANGUAGE_LOWER"] == "python"
    assert ctx["ENTRY_POINT"] == "__main__.py"
    assert ctx["SHARED_COMPONENTS_DIR"] == "components"
    assert ctx["SECRET_PROVIDER"] == "default"
    assert "Pulumi Cloud" in ctx["STATE_BACKEND_PATTERN"]
    assert "StackReference" in ctx["STACK_REFERENCE_PATTERN"]
    assert ctx["STACK_CONFIG_PATTERN"] == "Pulumi.{stack}.yaml"
    assert "pulumi up" in ctx["APPLY_COMMAND"]


# ---------------------------------------------------------------------------
# build_context — DATA_SOURCE_OVERRIDE cloud-specific values
# ---------------------------------------------------------------------------


def test_data_source_override_azure():
    ctx = build_context({"CLOUD_PROVIDER": "Azure"})
    override = ctx["DATA_SOURCE_OVERRIDE"]
    assert "azurerm_subscription" in override
    assert "subscription_id" in override
    assert "tenant_id" in override


def test_data_source_override_aws():
    ctx = build_context({"CLOUD_PROVIDER": "AWS"})
    override = ctx["DATA_SOURCE_OVERRIDE"]
    assert "aws_caller_identity" in override
    assert "account_id" in override
    assert "arn" in override
    assert "user_id" in override


def test_data_source_override_gcp():
    ctx = build_context({"CLOUD_PROVIDER": "GCP"})
    override = ctx["DATA_SOURCE_OVERRIDE"]
    assert "google_project" in override
    assert "project_id" in override
    assert "number" in override


# ---------------------------------------------------------------------------
# build_context — DESTROY_PIPELINE
# ---------------------------------------------------------------------------


def test_destroy_pipeline_github_actions():
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "CI_CD_PLATFORM": "GitHub Actions",
        "ORCHESTRATION_TOOL": "Terragrunt",
    })
    assert "DESTROY_PIPELINE" in ctx
    assert "workflow_dispatch" in ctx["DESTROY_PIPELINE"]
    assert "DESTROY" in ctx["DESTROY_PIPELINE"]
    assert "terragrunt run-all" in ctx["DESTROY_PIPELINE"]
    assert "${{ github.event.inputs.environment }}" in ctx["DESTROY_PIPELINE"]
    assert "${{ github.event.inputs.component }}" in ctx["DESTROY_PIPELINE"]


# ---------------------------------------------------------------------------
# build_context — CI/CD defaults
# ---------------------------------------------------------------------------


def test_build_context_github_actions_defaults():
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "CI_CD_PLATFORM": "GitHub Actions",
    })
    assert ctx["PIPELINE_DIR"] == ".github/workflows"


def test_build_context_gitlab_ci_defaults():
    ctx = build_context({
        "CLOUD_PROVIDER": "Azure",
        "CI_CD_PLATFORM": "GitLab CI",
    })
    assert ctx["PIPELINE_DIR"] == "."
    assert "include" in ctx["TEMPLATE_REFERENCE_PATTERN"]
