"""Tests for bootstrap_iac.interview — build_context."""

import pytest

from bootstrap_iac.interview import build_context


# ---------------------------------------------------------------------------
# build_context — cloud-specific defaults
# ---------------------------------------------------------------------------


def test_build_context_azure_defaults():
    ctx = build_context({"CLOUD_PROVIDER": "Azure", "COMPANY_NAME": "TestCo"})
    assert ctx["PROVIDER_NAME"] == "azurerm"
    assert ctx["TAG_ATTRIBUTE"] == "tags"
    assert "azurerm" in ctx["PROVIDER_BLOCK"]


def test_build_context_aws_defaults():
    ctx = build_context({"CLOUD_PROVIDER": "AWS", "COMPANY_NAME": "TestCo"})
    assert ctx["PROVIDER_NAME"] == "aws"
    assert ctx["TAG_ATTRIBUTE"] == "tags"
    assert "aws" in ctx["PROVIDER_BLOCK"]


def test_build_context_gcp_defaults():
    ctx = build_context({"CLOUD_PROVIDER": "GCP", "COMPANY_NAME": "TestCo"})
    assert ctx["PROVIDER_NAME"] == "google"
    assert ctx["TAG_ATTRIBUTE"] == "labels"
    assert "google" in ctx["PROVIDER_BLOCK"]


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
# build_context — DATA_SOURCE_OVERRIDE {resource} replacement
# ---------------------------------------------------------------------------


def test_data_source_override_azure_replaces_resource():
    ctx = build_context({"CLOUD_PROVIDER": "Azure"})
    assert "{resource}" not in ctx["DATA_SOURCE_OVERRIDE"]
    assert "azurerm_client_config" in ctx["DATA_SOURCE_OVERRIDE"]


def test_data_source_override_aws_replaces_resource():
    ctx = build_context({"CLOUD_PROVIDER": "AWS"})
    assert "{resource}" not in ctx["DATA_SOURCE_OVERRIDE"]
    assert "aws_caller_identity" in ctx["DATA_SOURCE_OVERRIDE"]


def test_data_source_override_gcp_replaces_resource():
    ctx = build_context({"CLOUD_PROVIDER": "GCP"})
    assert "{resource}" not in ctx["DATA_SOURCE_OVERRIDE"]
    assert "google_client_config" in ctx["DATA_SOURCE_OVERRIDE"]


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
