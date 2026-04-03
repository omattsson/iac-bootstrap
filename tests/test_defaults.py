"""Tests for bootstrap_iac.defaults — cloud/orchestration/CI-CD default values."""

from __future__ import annotations

import pytest

from bootstrap_iac.defaults import (
    AUTH_DEFAULTS,
    CICD_DEFAULTS,
    CLOUD_DEFAULTS,
    ORCHESTRATION_DEFAULTS,
)


class TestCloudDefaults:
    """CLOUD_DEFAULTS covers all three supported clouds with required keys."""

    REQUIRED_KEYS = [
        "provider_name",
        "provider_resource_example",
        "location_attribute",
        "state_backend",
        "provider_version_constraints",
        "standard_variables_default",
        "naming_pattern_default",
        "tag_merge_pattern",
        "data_source_override",
        "optional_features",
    ]

    @pytest.mark.parametrize("cloud", ["Azure", "AWS", "GCP"])
    def test_all_required_keys_present(self, cloud):
        cfg = CLOUD_DEFAULTS[cloud]
        for key in self.REQUIRED_KEYS:
            assert key in cfg, f"CLOUD_DEFAULTS[{cloud!r}] missing key: {key!r}"

    def test_azure_provider_name(self):
        assert CLOUD_DEFAULTS["Azure"]["provider_name"] == "azurerm"

    def test_aws_provider_name(self):
        assert CLOUD_DEFAULTS["AWS"]["provider_name"] == "aws"

    def test_gcp_provider_name(self):
        assert CLOUD_DEFAULTS["GCP"]["provider_name"] == "google"

    def test_all_standard_variables_are_non_empty(self):
        for cloud in CLOUD_DEFAULTS:
            assert CLOUD_DEFAULTS[cloud]["standard_variables_default"].strip()


class TestOrchestrationDefaults:
    """ORCHESTRATION_DEFAULTS covers Terragrunt, Terramate, and None."""

    REQUIRED_KEYS = [
        "lower",
        "validate_command",
        "plan_command",
        "plan_all_command",
        "plan_single_command",
        "graph_command",
        "envcommon_pattern",
        "environment_hierarchy",
        "hierarchy_diagram",
        "hierarchy_files_description",
        "input_flow_diagram",
        "component_config_pattern",
        "envcommon_template",
        "mock_outputs_example",
        "dependency_conventions",
    ]

    @pytest.mark.parametrize("tool", ["Terragrunt", "Terramate", "None"])
    def test_all_required_keys_present(self, tool):
        cfg = ORCHESTRATION_DEFAULTS[tool]
        for key in self.REQUIRED_KEYS:
            assert key in cfg, f"ORCHESTRATION_DEFAULTS[{tool!r}] missing key: {key!r}"

    def test_terragrunt_lower(self):
        assert ORCHESTRATION_DEFAULTS["Terragrunt"]["lower"] == "terragrunt"

    def test_terramate_lower(self):
        assert ORCHESTRATION_DEFAULTS["Terramate"]["lower"] == "terramate"

    def test_none_lower(self):
        assert ORCHESTRATION_DEFAULTS["None"]["lower"] == "terraform"

    def test_terragrunt_commands_contain_terragrunt(self):
        cfg = ORCHESTRATION_DEFAULTS["Terragrunt"]
        assert "terragrunt" in cfg["plan_command"]
        assert "terragrunt" in cfg["validate_command"]

    def test_none_commands_contain_terraform(self):
        cfg = ORCHESTRATION_DEFAULTS["None"]
        assert "terraform" in cfg["plan_command"]


class TestCicdDefaults:
    """CICD_DEFAULTS covers all four CI/CD platforms."""

    REQUIRED_KEYS = [
        "pipeline_dir",
        "pipeline_apply_to",
        "template_reference_pattern",
        "standard_parameters",
        "standard_parameters_list",
        "pipeline_conventions",
        "pipeline_conventions_list",
    ]

    @pytest.mark.parametrize("platform", ["GitHub Actions", "Azure DevOps", "GitLab CI", "Atlantis"])
    def test_all_required_keys_present(self, platform):
        cfg = CICD_DEFAULTS[platform]
        for key in self.REQUIRED_KEYS:
            assert key in cfg, f"CICD_DEFAULTS[{platform!r}] missing key: {key!r}"

    def test_github_actions_pipeline_dir(self):
        assert CICD_DEFAULTS["GitHub Actions"]["pipeline_dir"] == ".github/workflows"

    def test_azure_devops_pipeline_dir(self):
        assert CICD_DEFAULTS["Azure DevOps"]["pipeline_dir"] == "pipelines"


class TestAuthDefaults:
    """AUTH_DEFAULTS covers common cloud+CI/CD combinations."""

    @pytest.mark.parametrize(
        "cloud,cicd",
        [
            ("Azure", "GitHub Actions"),
            ("Azure", "Azure DevOps"),
            ("AWS", "GitHub Actions"),
            ("GCP", "GitHub Actions"),
        ],
    )
    def test_auth_defaults_have_required_keys(self, cloud, cicd):
        assert cloud in AUTH_DEFAULTS
        assert cicd in AUTH_DEFAULTS[cloud]
        entry = AUTH_DEFAULTS[cloud][cicd]
        assert "auth_pattern" in entry
        assert "auth_requirements" in entry

    def test_azure_github_uses_oidc(self):
        auth = AUTH_DEFAULTS["Azure"]["GitHub Actions"]["auth_pattern"]
        assert "OIDC" in auth or "oidc" in auth.lower() or "federated" in auth.lower()

    def test_aws_github_uses_oidc_or_role(self):
        auth = AUTH_DEFAULTS["AWS"]["GitHub Actions"]["auth_pattern"]
        assert "role" in auth.lower() or "oidc" in auth.lower()
