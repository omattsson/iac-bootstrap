"""Tests for bootstrap_iac.interview."""

import pytest

from bootstrap_iac.discovery import DiscoveryResult
from bootstrap_iac.interview import build_context, run_interview
from pathlib import Path


# ---------------------------------------------------------------------------
# Helper: create a full set of interview answers
# ---------------------------------------------------------------------------


def _make_answers(cloud="Azure", orch="Terragrunt", cicd="GitHub Actions", **extra):
    base = {
        "COMPANY_NAME": "TestCo",
        "CLOUD_PROVIDER": cloud,
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": orch,
        "ORCHESTRATION_DIR": "infra",
        "CI_CD_PLATFORM": cicd,
        "AUTH_PATTERN": "",
        "STATE_BACKEND": "",
        "NAMING_PATTERN": "",
        "TAG_STRATEGY": "",
        "STANDARD_VARIABLES": "",
        "TARGET": "both",
        "ORG": "testco",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# build_context — cloud-derived values
# ---------------------------------------------------------------------------


class TestBuildContextCloud:
    def test_azure_provider_name(self):
        ctx = build_context(_make_answers(cloud="Azure"))
        assert ctx["PROVIDER_NAME"] == "azurerm"

    def test_aws_provider_name(self):
        ctx = build_context(_make_answers(cloud="AWS"))
        assert ctx["PROVIDER_NAME"] == "aws"

    def test_gcp_provider_name(self):
        ctx = build_context(_make_answers(cloud="GCP"))
        assert ctx["PROVIDER_NAME"] == "google"

    def test_azure_tag_attribute(self):
        ctx = build_context(_make_answers(cloud="Azure"))
        assert ctx["TAG_ATTRIBUTE"] == "tags"

    def test_gcp_uses_labels(self):
        ctx = build_context(_make_answers(cloud="GCP"))
        assert ctx["TAG_ATTRIBUTE"] == "labels"
        assert ctx["TAG_LOCAL_REF"] == "local.labels"

    def test_provider_block_contains_source(self):
        ctx = build_context(_make_answers(cloud="AWS"))
        assert "hashicorp/aws" in ctx["PROVIDER_BLOCK"]

    def test_provider_version_constraints_populated(self):
        ctx = build_context(_make_answers(cloud="GCP"))
        assert "google" in ctx["PROVIDER_VERSION_CONSTRAINTS"]

    def test_private_endpoint_pattern_per_cloud(self):
        azure_ctx = build_context(_make_answers(cloud="Azure"))
        assert "azurerm_private_endpoint" in azure_ctx["PRIVATE_ENDPOINT_PATTERN"]

        aws_ctx = build_context(_make_answers(cloud="AWS"))
        assert "VPC" in aws_ctx["PRIVATE_ENDPOINT_PATTERN"]

        gcp_ctx = build_context(_make_answers(cloud="GCP"))
        assert "Private Service Connect" in gcp_ctx["PRIVATE_ENDPOINT_PATTERN"]


# ---------------------------------------------------------------------------
# build_context — orchestration-derived values
# ---------------------------------------------------------------------------


class TestBuildContextOrchestration:
    def test_terragrunt_derived_values(self):
        ctx = build_context(_make_answers(orch="Terragrunt"))
        assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terragrunt"
        assert ctx["VALIDATE_COMMAND"] == "terragrunt validate"
        assert ctx["PLAN_COMMAND"] == "terragrunt plan"

    def test_terramate_derived_values(self):
        ctx = build_context(_make_answers(orch="Terramate"))
        assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terramate"
        assert "terramate run" in ctx["VALIDATE_COMMAND"]

    def test_no_orchestration_derived_values(self):
        ctx = build_context(_make_answers(orch="None"))
        assert ctx["ORCHESTRATION_TOOL_LOWER"] == "terraform"
        assert ctx["VALIDATE_COMMAND"] == "terraform validate"

    def test_hierarchy_diagram_populated(self):
        ctx = build_context(_make_answers(orch="Terragrunt"))
        assert "subscription.hcl" in ctx["HIERARCHY_DIAGRAM"]

    def test_version_tag_location(self):
        ctx = build_context(_make_answers(orch="Terragrunt"))
        assert "subscription.hcl" in ctx["VERSION_TAG_LOCATION"]


# ---------------------------------------------------------------------------
# build_context — CI/CD-derived values
# ---------------------------------------------------------------------------


class TestBuildContextCiCd:
    def test_github_actions_pipeline_apply_to(self):
        ctx = build_context(_make_answers(cicd="GitHub Actions"))
        assert ctx["PIPELINE_APPLY_TO"] == ".github/workflows/**/*.yml"

    def test_azure_devops_pipeline_apply_to(self):
        ctx = build_context(_make_answers(cicd="Azure DevOps"))
        assert "pipelines" in ctx["PIPELINE_APPLY_TO"]

    def test_gitlab_ci_pipeline_apply_to(self):
        ctx = build_context(_make_answers(cicd="GitLab CI"))
        assert ".gitlab-ci.yml" in ctx["PIPELINE_APPLY_TO"]

    def test_atlantis_pipeline_apply_to(self):
        ctx = build_context(_make_answers(cicd="Atlantis"))
        assert "atlantis.yaml" in ctx["PIPELINE_APPLY_TO"]

    def test_auth_requirements_populated(self):
        ctx = build_context(_make_answers(cicd="GitHub Actions"))
        assert "OIDC" in ctx["AUTH_REQUIREMENTS"]


# ---------------------------------------------------------------------------
# build_context — module source pattern
# ---------------------------------------------------------------------------


class TestBuildContextModuleSource:
    def test_module_source_includes_org(self):
        ctx = build_context(_make_answers(ORG="acme"))
        assert "acme" in ctx["MODULE_SOURCE_PATTERN"]

    def test_module_source_includes_prefix(self):
        ctx = build_context(_make_answers(MODULE_PREFIX="terraform-aws"))
        assert "terraform-aws" in ctx["MODULE_SOURCE_PATTERN"]

    def test_module_source_convention_matches(self):
        ctx = build_context(_make_answers())
        assert ctx["MODULE_SOURCE_CONVENTION"] == ctx["MODULE_SOURCE_PATTERN"]


# ---------------------------------------------------------------------------
# build_context — pipeline snippets
# ---------------------------------------------------------------------------


class TestBuildContextPipelines:
    def test_single_component_pipeline_github(self):
        ctx = build_context(_make_answers(cicd="GitHub Actions"))
        assert "plan-apply" in ctx["SINGLE_COMPONENT_PIPELINE"]
        assert "testco" in ctx["SINGLE_COMPONENT_PIPELINE"]

    def test_stack_pipeline_terragrunt(self):
        ctx = build_context(_make_answers(orch="Terragrunt", cicd="GitHub Actions"))
        assert "terragrunt" in ctx["STACK_PIPELINE"]

    def test_drift_pipeline_populated(self):
        ctx = build_context(_make_answers(cicd="GitHub Actions"))
        assert "drift" in ctx["DRIFT_PIPELINE"].lower()


# ---------------------------------------------------------------------------
# build_context — naming and testing defaults
# ---------------------------------------------------------------------------


class TestBuildContextDefaults:
    def test_resource_identifier_default(self):
        ctx = build_context(_make_answers())
        assert ctx["RESOURCE_IDENTIFIER"] == "default"

    def test_common_vars_file_default(self):
        ctx = build_context(_make_answers())
        assert ctx["COMMON_VARS_FILE"] == "common.variables.tf"

    def test_data_source_override_uses_provider(self):
        ctx = build_context(_make_answers(cloud="AWS"))
        assert "aws" in ctx["DATA_SOURCE_OVERRIDE"]

    def test_environment_hierarchy_for_terragrunt(self):
        ctx = build_context(_make_answers(orch="Terragrunt"))
        assert "terragrunt.hcl" in ctx["ENVIRONMENT_HIERARCHY"]

    def test_environment_hierarchy_for_terramate(self):
        ctx = build_context(_make_answers(orch="Terramate"))
        assert "stack.tm.hcl" in ctx["ENVIRONMENT_HIERARCHY"]


# ---------------------------------------------------------------------------
# run_interview — non-interactive mode with overrides
# ---------------------------------------------------------------------------


def test_run_interview_non_interactive_uses_overrides(tmp_path):
    discovery = DiscoveryResult(workspace_path=tmp_path)
    overrides = {
        "COMPANY_NAME": "OverrideCo",
        "CLOUD_PROVIDER": "AWS",
        "MODULE_PREFIX": "terraform-aws",
        "ORCHESTRATION_TOOL": "None",
        "CI_CD_PLATFORM": "GitHub Actions",
        "TARGET": "copilot",
        "ORG": "overrideco",
    }
    answers = run_interview(discovery, non_interactive=True, overrides=overrides)
    assert answers["COMPANY_NAME"] == "OverrideCo"
    assert answers["CLOUD_PROVIDER"] == "AWS"
    assert answers["MODULE_PREFIX"] == "terraform-aws"
    assert answers["ORCHESTRATION_TOOL"] == "None"
    assert answers["TARGET"] == "copilot"


def test_run_interview_non_interactive_uses_discovery_defaults(tmp_path):
    discovery = DiscoveryResult(
        workspace_path=tmp_path,
        cloud_provider="GCP",
        orchestration_tool="Terramate",
        orchestration_dir="stacks",
        ci_cd_platform="GitLab CI",
        org_name="discovered-org",
    )
    answers = run_interview(discovery, non_interactive=True, overrides={})
    assert answers["CLOUD_PROVIDER"] == "GCP"
    assert answers["ORCHESTRATION_TOOL"] == "Terramate"
    assert answers["ORCHESTRATION_DIR"] == "stacks"
    assert answers["CI_CD_PLATFORM"] == "GitLab CI"


def test_run_interview_non_interactive_falls_back_to_defaults(tmp_path):
    """When nothing is detected and no overrides, sensible defaults are used."""
    discovery = DiscoveryResult(workspace_path=tmp_path)
    answers = run_interview(discovery, non_interactive=True, overrides={})
    assert answers["COMPANY_NAME"] == "MyOrg"
    assert answers["CLOUD_PROVIDER"] == "Azure"
    assert answers["MODULE_PREFIX"] == "tf-module"
    assert answers["ORCHESTRATION_TOOL"] == "None"
    assert answers["CI_CD_PLATFORM"] == "GitHub Actions"
    assert answers["TARGET"] == "both"


def test_run_interview_override_takes_precedence_over_discovery(tmp_path):
    """CLI overrides should beat discovered values."""
    discovery = DiscoveryResult(
        workspace_path=tmp_path,
        cloud_provider="AWS",
    )
    overrides = {"CLOUD_PROVIDER": "GCP"}
    answers = run_interview(discovery, non_interactive=True, overrides=overrides)
    assert answers["CLOUD_PROVIDER"] == "GCP"


def test_run_interview_no_orch_skips_orch_dir(tmp_path):
    """When orchestration is None, ORCHESTRATION_DIR gets a default."""
    discovery = DiscoveryResult(workspace_path=tmp_path)
    overrides = {"ORCHESTRATION_TOOL": "None"}
    answers = run_interview(discovery, non_interactive=True, overrides=overrides)
    assert answers["ORCHESTRATION_DIR"] == "."
