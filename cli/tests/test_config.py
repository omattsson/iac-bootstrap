"""Tests for config file support (.bootstrap-iac.yaml)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bootstrap_iac.config import find_config, load_config, write_config


# ---------------------------------------------------------------------------
# find_config
# ---------------------------------------------------------------------------


def test_find_config_yaml(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\n")
    assert find_config(tmp_path) == cfg


def test_find_config_yml(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yml"
    cfg.write_text("company: Acme\n")
    assert find_config(tmp_path) == cfg


def test_find_config_prefers_yaml_over_yml(tmp_path):
    (tmp_path / ".bootstrap-iac.yaml").write_text("company: Yaml\n")
    (tmp_path / ".bootstrap-iac.yml").write_text("company: Yml\n")
    assert find_config(tmp_path).name == ".bootstrap-iac.yaml"


def test_find_config_returns_none(tmp_path):
    assert find_config(tmp_path) is None


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_basic(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text(
        "company: Acme Corp\n"
        "cloud: azure\n"
        "module_prefix: tf-module\n"
        "orchestration: terragrunt\n"
        "ci_cd: github-actions\n"
        "org: acme\n"
        "target: both\n"
    )
    result = load_config(cfg)
    assert result["COMPANY_NAME"] == "Acme Corp"
    assert result["CLOUD_PROVIDER"] == "Azure"
    assert result["MODULE_PREFIX"] == "tf-module"
    assert result["ORCHESTRATION_TOOL"] == "Terragrunt"
    assert result["CI_CD_PLATFORM"] == "GitHub Actions"
    assert result["ORG"] == "acme"
    assert result["TARGET"] == "both"


def test_load_config_normalises_cloud_cases(tmp_path):
    for raw, expected in [("azure", "Azure"), ("AWS", "AWS"), ("gcp", "GCP")]:
        cfg = tmp_path / ".bootstrap-iac.yaml"
        cfg.write_text(f"cloud: {raw}\n")
        assert load_config(cfg)["CLOUD_PROVIDER"] == expected


def test_load_config_normalises_orchestration(tmp_path):
    for raw, expected in [
        ("terragrunt", "Terragrunt"),
        ("Terramate", "Terramate"),
        ("PULUMI", "Pulumi"),
        ("none", "None"),
    ]:
        cfg = tmp_path / ".bootstrap-iac.yaml"
        cfg.write_text(f"orchestration: {raw}\n")
        assert load_config(cfg)["ORCHESTRATION_TOOL"] == expected


def test_load_config_normalises_cicd(tmp_path):
    for raw, expected in [
        ("github-actions", "GitHub Actions"),
        ("azure-devops", "Azure DevOps"),
        ("gitlab-ci", "GitLab CI"),
        ("atlantis", "Atlantis"),
    ]:
        cfg = tmp_path / ".bootstrap-iac.yaml"
        cfg.write_text(f"ci_cd: {raw}\n")
        assert load_config(cfg)["CI_CD_PLATFORM"] == expected


def test_load_config_ignores_unknown_keys(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\nunknown_key: ignored\n")
    result = load_config(cfg)
    assert result == {"COMPANY_NAME": "Acme"}


def test_load_config_empty_file(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("")
    assert load_config(cfg) == {}


def test_load_config_rejects_non_mapping(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("- item1\n- item2\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_config(cfg)


def test_load_config_all_fields(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text(
        "company: Test Corp\n"
        "cloud: aws\n"
        "module_prefix: terraform-aws\n"
        "orchestration: none\n"
        "orchestration_dir: infra\n"
        "ci_cd: gitlab-ci\n"
        "auth: OIDC\n"
        "state_backend: S3\n"
        "naming: prefix-type-suffix\n"
        "tag_strategy: merge tags\n"
        "org: testorg\n"
        "target: copilot\n"
    )
    result = load_config(cfg)
    assert result["COMPANY_NAME"] == "Test Corp"
    assert result["CLOUD_PROVIDER"] == "AWS"
    assert result["MODULE_PREFIX"] == "terraform-aws"
    assert result["ORCHESTRATION_TOOL"] == "None"
    assert result["ORCHESTRATION_DIR"] == "infra"
    assert result["CI_CD_PLATFORM"] == "GitLab CI"
    assert result["AUTH_PATTERN"] == "OIDC"
    assert result["STATE_BACKEND"] == "S3"
    assert result["NAMING_PATTERN"] == "prefix-type-suffix"
    assert result["TAG_STRATEGY"] == "merge tags"
    assert result["ORG"] == "testorg"
    assert result["TARGET"] == "copilot"


# ---------------------------------------------------------------------------
# write_config
# ---------------------------------------------------------------------------


def test_write_config_roundtrip(tmp_path):
    answers = {
        "COMPANY_NAME": "Acme Corp",
        "CLOUD_PROVIDER": "Azure",
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": "Terragrunt",
        "ORCHESTRATION_DIR": "infrastructure-config",
        "CI_CD_PLATFORM": "GitHub Actions",
        "AUTH_PATTERN": "OIDC",
        "STATE_BACKEND": "azurerm",
        "NAMING_PATTERN": "{prefix}-{resource_abbreviation}-{suffix}",
        "TAG_STRATEGY": "merge(var.env_default_tags, var.tags)",
        "ORG": "acme",
        "TARGET": "both",
    }
    out = tmp_path / ".bootstrap-iac.yaml"
    write_config(answers, out)

    assert out.exists()
    content = yaml.safe_load(out.read_text())
    assert content["company"] == "Acme Corp"
    assert content["cloud"] == "Azure"
    assert content["orchestration"] == "Terragrunt"
    assert content["ci_cd"] == "GitHub Actions"
    assert content["org"] == "acme"
    assert content["target"] == "both"


def test_write_config_skips_empty_values(tmp_path):
    answers = {
        "COMPANY_NAME": "Acme",
        "CLOUD_PROVIDER": "",
        "MODULE_PREFIX": "",
        "ORG": "acme",
    }
    out = tmp_path / ".bootstrap-iac.yaml"
    write_config(answers, out)

    content = yaml.safe_load(out.read_text())
    assert "company" in content
    assert "org" in content
    assert "cloud" not in content
    assert "module_prefix" not in content


def test_save_then_load_roundtrip(tmp_path):
    """write_config output can be loaded back via load_config."""
    answers = {
        "COMPANY_NAME": "RoundTrip Inc",
        "CLOUD_PROVIDER": "GCP",
        "MODULE_PREFIX": "tf-gcp",
        "ORCHESTRATION_TOOL": "None",
        "CI_CD_PLATFORM": "GitHub Actions",
        "ORG": "roundtrip",
        "TARGET": "claude",
    }
    out = tmp_path / ".bootstrap-iac.yaml"
    write_config(answers, out)

    loaded = load_config(out)
    assert loaded["COMPANY_NAME"] == "RoundTrip Inc"
    assert loaded["CLOUD_PROVIDER"] == "GCP"
    assert loaded["ORCHESTRATION_TOOL"] == "None"
    assert loaded["TARGET"] == "claude"


# ---------------------------------------------------------------------------
# CLI integration (config file loading via CliRunner)
# ---------------------------------------------------------------------------

from click.testing import CliRunner
from bootstrap_iac.cli import main

cli_runner = CliRunner()


def _make_workspace(tmp_path: Path) -> Path:
    (tmp_path / "main.tf").write_text('provider "azurerm" {\n  features {}\n}\n')
    return tmp_path


def test_cli_loads_config_file(tmp_path):
    """Config file values are used as defaults in non-interactive mode."""
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text(
        "company: ConfigCorp\n"
        "cloud: azure\n"
        "module_prefix: tf-mod\n"
        "orchestration: none\n"
        "ci_cd: github-actions\n"
        "org: configcorp\n"
        "target: copilot\n"
    )
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--output-dir", str(tmp_path / "out"),
        "--non-interactive",
    ])
    assert result.exit_code == 0
    assert "Loading config" in result.output
    assert "ConfigCorp" in result.output or (tmp_path / "out" / ".github").exists()


def test_cli_flag_overrides_config(tmp_path):
    """CLI flags take precedence over config file values."""
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text("company: ConfigCorp\ncloud: azure\ntarget: both\n")

    out_dir = tmp_path / "out"
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--output-dir", str(out_dir),
        "--company", "FlagCorp",
        "--target", "copilot",
        "--non-interactive",
    ])
    assert result.exit_code == 0
    # --target copilot overrides config target=both → only .github/, no CLAUDE.md
    assert (out_dir / ".github").is_dir()
    assert not (out_dir / "CLAUDE.md").exists()
    # --company FlagCorp overrides config company=ConfigCorp
    copilot_instructions = (out_dir / ".github" / "copilot-instructions.md").read_text()
    assert "FlagCorp" in copilot_instructions
    assert "ConfigCorp" not in copilot_instructions


def test_cli_explicit_config_path(tmp_path):
    """--config flag loads a specific config file."""
    ws = _make_workspace(tmp_path)
    cfg = tmp_path / "custom-config.yaml"
    cfg.write_text(
        "company: CustomCfg\n"
        "cloud: aws\n"
        "orchestration: none\n"
        "ci_cd: github-actions\n"
        "target: claude\n"
    )
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--output-dir", str(tmp_path / "out"),
        "--config", str(cfg),
        "--non-interactive",
    ])
    assert result.exit_code == 0
    assert "Loading config" in result.output


def test_cli_config_not_found(tmp_path):
    """--config with a nonexistent path exits with error."""
    ws = _make_workspace(tmp_path)
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--config", str(tmp_path / "nonexistent.yaml"),
        "--non-interactive",
    ])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_cli_save_config(tmp_path):
    """--save-config writes a .bootstrap-iac.yaml to the workspace."""
    ws = _make_workspace(tmp_path)
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--company", "SaveCorp",
        "--cloud", "azure",
        "--orchestration", "none",
        "--ci-cd", "github-actions",
        "--target", "copilot",
        "--non-interactive",
        "--save-config",
    ])
    assert result.exit_code == 0
    cfg_out = ws / ".bootstrap-iac.yaml"
    assert cfg_out.exists()
    content = yaml.safe_load(cfg_out.read_text())
    assert content["company"] == "SaveCorp"
    assert content["cloud"] == "Azure"


def test_cli_save_config_not_written_on_dry_run(tmp_path):
    """--save-config with --dry-run should not write the config file."""
    ws = _make_workspace(tmp_path)
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--company", "DryRunCorp",
        "--cloud", "azure",
        "--orchestration", "none",
        "--ci-cd", "github-actions",
        "--target", "copilot",
        "--non-interactive",
        "--save-config",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert not (ws / ".bootstrap-iac.yaml").exists()
