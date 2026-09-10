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


def test_detect_cloud_provider_ignores_commented_out(tmp_path):
    """Commented-out provider blocks should not be detected."""
    (tmp_path / "main.tf").write_text(textwrap.dedent("""\
        # provider "aws" {
        #   region = "us-east-1"
        # }
    """))
    assert _detect_cloud_provider(tmp_path) is None


def test_detect_cloud_provider_ignores_block_comment(tmp_path):
    """Provider blocks inside /* ... */ should not be detected."""
    (tmp_path / "main.tf").write_text(textwrap.dedent("""\
        /*
        provider "aws" {
          region = "us-east-1"
        }
        */
    """))
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


def test_detect_cloud_provider_ignores_bare_key_in_locals(tmp_path):
    """A bare 'aws = { ... }' in locals should not trigger cloud detection."""
    (tmp_path / "locals.tf").write_text(textwrap.dedent("""\
        locals {
          aws = {
            region = "us-east-1"
          }
        }
    """))
    assert _detect_cloud_provider(tmp_path) is None


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


def test_detect_orchestration_ignores_terragrunt_cache(tmp_path):
    cache = tmp_path / ".terragrunt-cache" / "abc"
    cache.mkdir(parents=True)
    (cache / "terragrunt.hcl").write_text("# cached\n")
    tool, orch_dir = _detect_orchestration(tmp_path)
    assert tool is None
    assert orch_dir is None


def test_detect_orchestration_prefers_real_over_cache(tmp_path):
    # Real config
    real = tmp_path / "infra" / "dev"
    real.mkdir(parents=True)
    (real / "terragrunt.hcl").write_text("# real\n")
    # Cached copy
    cache = tmp_path / ".terragrunt-cache" / "abc"
    cache.mkdir(parents=True)
    (cache / "terragrunt.hcl").write_text("# cached\n")
    tool, orch_dir = _detect_orchestration(tmp_path)
    assert tool == "Terragrunt"
    assert orch_dir == "infra"


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
    assert _detect_state_backend(tmp_path) == "Terraform Cloud / Enterprise"


def test_detect_state_backend_none(tmp_path):
    (tmp_path / "main.tf").write_text("resource \"null_resource\" \"x\" {}\n")
    assert _detect_state_backend(tmp_path) is None


def test_detect_state_backend_ignores_commented_out(tmp_path):
    """Commented-out backend blocks should not be detected."""
    (tmp_path / "backend.tf").write_text(textwrap.dedent("""\
        terraform {
          # backend "s3" {
          #   bucket = "old-bucket"
          # }
        }
    """))
    assert _detect_state_backend(tmp_path) is None


def test_detect_state_backend_ignores_block_comment(tmp_path):
    """Backend blocks inside /* ... */ should not be detected."""
    (tmp_path / "backend.tf").write_text(textwrap.dedent("""\
        /*
        terraform {
          backend "s3" {
            bucket = "old-bucket"
          }
        }
        */
    """))
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
    result = _detect_naming_pattern(tmp_path)
    assert result is not None
    assert "prefix" in result


def test_detect_naming_pattern_format_style(tmp_path):
    (tmp_path / "locals.tf").write_text(textwrap.dedent("""\
        locals {
          name = format("%s-rg-%s", var.prefix, var.suffix)
        }
    """))
    assert _detect_naming_pattern(tmp_path) is not None


def test_detect_naming_pattern_ignores_commented_out(tmp_path):
    (tmp_path / "locals.tf").write_text(textwrap.dedent("""\
        # name = "${var.prefix}-rg-${var.suffix}"
        // name = format("%s-rg-%s", var.prefix, var.suffix)
    """))
    assert _detect_naming_pattern(tmp_path) is None


def test_detect_naming_pattern_ignores_block_comment(tmp_path):
    (tmp_path / "locals.tf").write_text(textwrap.dedent("""\
        /*
        name = "${var.prefix}-rg-${var.suffix}"
        name = format("%s-rg-%s", var.prefix, var.suffix)
        */
    """))
    assert _detect_naming_pattern(tmp_path) is None


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
    # The presence flag is also traceable in the machine-readable signals.
    assert any(s.field == "has_copilot_instructions" for s in result.signals)


def test_scan_workspace_detects_existing_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Claude\n")
    result = scan_workspace(tmp_path)
    assert result.has_claude_md is True
    assert any("CLAUDE.md" in n for n in result.notes)


# ---------------------------------------------------------------------------
# Evidence, confidence, and multi-cloud (issue #61)
# ---------------------------------------------------------------------------


def test_multi_cloud_reported_not_collapsed(tmp_path):
    """A workspace with two providers reports both, not just the winner."""
    (tmp_path / "azure.tf").write_text('provider "azurerm" {}\n')
    (tmp_path / "aws1.tf").write_text('provider "aws" {}\n')
    (tmp_path / "aws2.tf").write_text('provider "aws" {}\n')
    result = scan_workspace(tmp_path)
    # AWS has more signals, so it is primary, but Azure is still reported.
    assert result.cloud_provider == "AWS"
    assert set(result.cloud_providers) == {"AWS", "Azure"}
    assert result.cloud_providers[0] == "AWS"  # ordered by signal count
    assert any("Multiple cloud providers" in n for n in result.notes)


def test_single_cloud_has_no_multi_note(tmp_path):
    (tmp_path / "main.tf").write_text('provider "azurerm" {}\n')
    result = scan_workspace(tmp_path)
    assert result.cloud_providers == ["Azure"]
    assert not any("Multiple cloud providers" in n for n in result.notes)


def test_cloud_tie_break_prefers_canonical_order(tmp_path):
    """On an equal-count tie the primary is Azure > AWS > GCP (stable)."""
    (tmp_path / "a.tf").write_text('provider "aws" {}\n')
    (tmp_path / "b.tf").write_text('provider "azurerm" {}\n')
    result = scan_workspace(tmp_path)
    assert result.cloud_provider == "Azure"
    assert set(result.cloud_providers) == {"Azure", "AWS"}


def test_provider_in_both_blocks_counts_once_per_file(tmp_path):
    """A provider in both a provider block and required_providers counts once."""
    (tmp_path / "main.tf").write_text(
        'terraform {\n'
        '  required_providers {\n'
        '    azurerm = {\n'
        '      source = "hashicorp/azurerm"\n'
        '    }\n'
        '  }\n'
        '}\n'
        'provider "azurerm" {}\n'
    )
    result = scan_workspace(tmp_path)
    azure_signals = [
        s for s in result.signals if s.field == "cloud_provider" and s.value == "Azure"
    ]
    assert len(azure_signals) == 1


def test_every_inferred_value_has_a_signal(tmp_path):
    """Each inferred field can be traced to a file/signal."""
    (tmp_path / "main.tf").write_text('provider "azurerm" {}\n')
    (tmp_path / "backend.tf").write_text('terraform {\n  backend "s3" {}\n}\n')
    result = scan_workspace(tmp_path)
    fields = {s.field for s in result.signals}
    assert "cloud_provider" in fields
    assert "state_backend" in fields
    # The cloud signal names the file it came from.
    cloud_sig = next(s for s in result.signals if s.field == "cloud_provider")
    assert cloud_sig.source == "main.tf"
    assert cloud_sig.value == "Azure"
    assert "azurerm" in cloud_sig.detail


def test_orchestration_and_pipeline_dirs_have_signals(tmp_path):
    """The inferred dir fields are also traceable to a source file."""
    cfg = tmp_path / "infrastructure-config" / "dev"
    cfg.mkdir(parents=True)
    (cfg / "terragrunt.hcl").write_text("# root\n")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("on: push\n")

    result = scan_workspace(tmp_path)
    fields = {s.field for s in result.signals}
    assert "orchestration_dir" in fields
    assert "pipeline_dir" in fields
    orch_dir_sig = next(s for s in result.signals if s.field == "orchestration_dir")
    assert orch_dir_sig.source == "infrastructure-config/dev/terragrunt.hcl"


def test_signal_source_is_nested_file(tmp_path):
    """Signals point at the actual nested file, not just the workspace root."""
    nested = tmp_path / "modules" / "network"
    nested.mkdir(parents=True)
    (nested / "provider.tf").write_text('provider "google" {}\n')
    result = scan_workspace(tmp_path)
    assert result.cloud_provider == "GCP"
    sig = next(s for s in result.signals if s.field == "cloud_provider")
    assert sig.source == "modules/network/provider.tf"


# ---------------------------------------------------------------------------
# CI/CD: empty workflow dir and YAML extensions (issue #61)
# ---------------------------------------------------------------------------


def test_empty_workflows_dir_is_not_github_actions(tmp_path):
    """An empty .github/workflows/ must not be classified as GitHub Actions."""
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform is None
    assert pipeline_dir is None


def test_github_actions_yaml_extension(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yaml").write_text("on: push\n")
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform == "GitHub Actions"


def test_azure_pipelines_yaml_extension(tmp_path):
    (tmp_path / "azure-pipelines.yaml").write_text("trigger:\n  - main\n")
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform == "Azure DevOps"
    assert pipeline_dir == "."


def test_gitlab_ci_yaml_extension(tmp_path):
    (tmp_path / ".gitlab-ci.yaml").write_text("stages:\n  - build\n")
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform == "GitLab CI"


def test_generic_pipelines_dir_detected(tmp_path):
    """A pipelines/ directory of YAML is detected (workspace-relative)."""
    pipe = tmp_path / "ci" / "pipelines"
    pipe.mkdir(parents=True)
    (pipe / "deploy.yaml").write_text("steps: []\n")
    platform, pipeline_dir = _detect_ci_cd(tmp_path)
    assert platform == "Unknown"
    assert pipeline_dir == "ci/pipelines"


def test_pipelines_segment_in_checkout_path_is_not_a_signal(tmp_path):
    """A `pipelines` segment above the workspace must not fabricate a signal."""
    workspace = tmp_path / "pipelines" / "repo"
    workspace.mkdir(parents=True)
    (workspace / "values.yaml").write_text("foo: bar\n")
    platform, pipeline_dir = _detect_ci_cd(workspace)
    assert platform is None


# ---------------------------------------------------------------------------
# Ignored directories and configurable ignores (issue #61)
# ---------------------------------------------------------------------------


def test_ignores_node_modules_by_default(tmp_path):
    """A provider inside node_modules is not a real signal."""
    vendored = tmp_path / "node_modules" / "some-pkg"
    vendored.mkdir(parents=True)
    (vendored / "main.tf").write_text('provider "aws" {}\n')
    result = scan_workspace(tmp_path)
    assert result.cloud_provider is None
    assert result.cloud_providers == []


def test_custom_ignored_dir(tmp_path):
    """A caller can add extra ignored directories."""
    (tmp_path / "real.tf").write_text('provider "azurerm" {}\n')
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "aws.tf").write_text('provider "aws" {}\n')

    # Without the ignore, both providers are seen.
    both = scan_workspace(tmp_path)
    assert set(both.cloud_providers) == {"Azure", "AWS"}

    # With "vendor" ignored, only the real provider remains.
    filtered = scan_workspace(tmp_path, ignored_dirs=["vendor"])
    assert filtered.cloud_providers == ["Azure"]


def test_orchestration_ignores_pruned_dirs(tmp_path):
    """A terragrunt.hcl inside an ignored dir is not detected."""
    cache = tmp_path / ".terragrunt-cache" / "abc"
    cache.mkdir(parents=True)
    (cache / "terragrunt.hcl").write_text("# cached\n")
    tool, _dir = _detect_orchestration(tmp_path)
    assert tool is None


# ---------------------------------------------------------------------------
# Machine-readable output (issue #61)
# ---------------------------------------------------------------------------


def test_to_dict_is_json_serialisable(tmp_path):
    import json

    (tmp_path / "main.tf").write_text('provider "azurerm" {}\n')
    result = scan_workspace(tmp_path)
    data = result.to_dict()
    # Round-trips through JSON without error.
    reparsed = json.loads(json.dumps(data))
    assert reparsed["cloud_provider"] == "Azure"
    assert reparsed["cloud_providers"] == ["Azure"]
    assert isinstance(reparsed["signals"], list)
    assert reparsed["signals"][0]["source"] == "main.tf"
