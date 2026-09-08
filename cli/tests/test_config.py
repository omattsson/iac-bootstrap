"""Tests for config file support (.bootstrap-iac.yaml)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from click.testing import CliRunner

from bootstrap_iac.cli import main
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


def test_load_config_rejects_unknown_key(tmp_path):
    """A misspelled/unknown key must fail loudly, not be silently ignored."""
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\nclould: azure\n")
    with pytest.raises(ValueError) as exc_info:
        load_config(cfg)
    message = str(exc_info.value)
    assert "clould" in message
    assert "Supported keys" in message


def test_load_config_reports_all_unknown_keys(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\nfoo: 1\nbar: 2\n")
    with pytest.raises(ValueError) as exc_info:
        load_config(cfg)
    message = str(exc_info.value)
    assert "foo" in message
    assert "bar" in message


def test_load_config_accepts_supported_version(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("version: '1'\ncompany: Acme\n")
    result = load_config(cfg)
    # version is a meta key, not an override.
    assert result == {"COMPANY_NAME": "Acme"}


def test_load_config_accepts_numeric_version(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("version: 1\ncompany: Acme\n")
    result = load_config(cfg)
    assert result == {"COMPANY_NAME": "Acme"}


def test_load_config_accepts_float_version(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("version: 1.0\ncompany: Acme\n")
    result = load_config(cfg)
    assert result == {"COMPANY_NAME": "Acme"}


def test_load_config_version_only(tmp_path):
    """A config with only a version key is valid and yields no overrides."""
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("version: '1'\n")
    assert load_config(cfg) == {}


def test_load_config_rejects_unsupported_version(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("version: '2'\ncompany: Acme\n")
    with pytest.raises(ValueError) as exc_info:
        load_config(cfg)
    message = str(exc_info.value)
    assert "version" in message
    assert "'2'" in message
    # The accepted values must be named.
    assert "1" in message


def test_load_config_rejects_non_string_key(tmp_path):
    """A non-string YAML key is unknown and errors rather than being ignored."""
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\n1: oops\n")
    with pytest.raises(ValueError, match="Unknown config key"):
        load_config(cfg)


def test_load_config_empty_file(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("")
    assert load_config(cfg) == {}


def test_load_config_rejects_non_mapping(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("- item1\n- item2\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_config(cfg)


def test_load_config_rejects_invalid_cloud(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("cloud: digitalocean\n")
    with pytest.raises(ValueError, match="unsupported value 'digitalocean'"):
        load_config(cfg)


def test_load_config_rejects_invalid_orchestration(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("orchestration: spacelift\n")
    with pytest.raises(ValueError, match="unsupported value 'spacelift'"):
        load_config(cfg)


def test_load_config_rejects_invalid_cicd(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("ci_cd: jenkins\n")
    with pytest.raises(ValueError, match="unsupported value 'jenkins'"):
        load_config(cfg)


def test_load_config_rejects_invalid_target(tmp_path):
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("target: vscode\n")
    with pytest.raises(ValueError, match="unsupported value 'vscode'"):
        load_config(cfg)


def test_load_config_null_value_is_unset(tmp_path):
    """A YAML null for a known key is treated as unset, not an error."""
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\ncloud: null\n")
    result = load_config(cfg)
    assert result == {"COMPANY_NAME": "Acme"}
    assert "CLOUD_PROVIDER" not in result


def test_load_config_rejects_non_scalar_value(tmp_path):
    """A list/mapping value for a scalar key names the key."""
    cfg = tmp_path / ".bootstrap-iac.yaml"
    cfg.write_text("company:\n  - a\n  - b\n")
    with pytest.raises(ValueError) as exc_info:
        load_config(cfg)
    message = str(exc_info.value)
    assert "company" in message
    assert "scalar" in message


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
        "standard_variables: prefix, location, tags\n"
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
    assert result["STANDARD_VARIABLES"] == "prefix, location, tags"
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
        "STANDARD_VARIABLES": "- prefix\n- location\n- tags",
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
    out_dir = tmp_path / "out"
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--output-dir", str(out_dir),
        "--non-interactive",
    ])
    assert result.exit_code == 0
    assert "Loading config" in result.output

    copilot_instructions = out_dir / ".github" / "copilot-instructions.md"
    assert copilot_instructions.is_file()

    rendered = copilot_instructions.read_text()
    assert "ConfigCorp" in rendered
    assert "Azure" in rendered


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


def test_cli_save_config_refuses_overwrite(tmp_path):
    """--save-config without --overwrite refuses to overwrite existing config."""
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text("company: Original\n")
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--company", "NewCorp",
        "--cloud", "azure",
        "--orchestration", "none",
        "--ci-cd", "github-actions",
        "--target", "copilot",
        "--non-interactive",
        "--save-config",
    ])
    assert result.exit_code == 0
    assert "Refusing to overwrite" in result.output
    # Original config should be unchanged
    assert yaml.safe_load(cfg.read_text())["company"] == "Original"


def test_cli_save_config_overwrites_with_flag(tmp_path):
    """--save-config with --overwrite replaces existing config."""
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text("company: Original\n")
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--company", "NewCorp",
        "--cloud", "azure",
        "--orchestration", "none",
        "--ci-cd", "github-actions",
        "--target", "copilot",
        "--non-interactive",
        "--save-config",
        "--overwrite",
    ])
    assert result.exit_code == 0
    assert "Saved config" in result.output
    assert yaml.safe_load(cfg.read_text())["company"] == "NewCorp"


def test_cli_save_config_writes_to_detected_yml(tmp_path):
    """--save-config writes back to detected .yml file, not creating a new .yaml."""
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yml"
    cfg.write_text("company: Original\n")
    result = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--company", "YmlCorp",
        "--cloud", "aws",
        "--orchestration", "none",
        "--ci-cd", "github-actions",
        "--target", "copilot",
        "--non-interactive",
        "--save-config",
        "--overwrite",
    ])
    assert result.exit_code == 0
    assert "Saved config" in result.output
    # Should have written to .yml, not created .yaml
    assert cfg.exists()
    assert not (ws / ".bootstrap-iac.yaml").exists()
    assert yaml.safe_load(cfg.read_text())["company"] == "YmlCorp"


# ---------------------------------------------------------------------------
# --check-config
# ---------------------------------------------------------------------------


def test_cli_check_config_valid(tmp_path):
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text("version: '1'\ncompany: Acme\ncloud: azure\n")
    result = cli_runner.invoke(main, ["--workspace", str(ws), "--check-config"])
    assert result.exit_code == 0
    assert "Config is valid" in result.output
    # Resolved values are shown with config-file keys, and normalisation is
    # visible (the config's `cloud: azure` is displayed as `cloud = Azure`).
    assert "company = Acme" in result.output
    assert "cloud = Azure" in result.output


def test_cli_check_config_invalid_unknown_key(tmp_path):
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\nclould: azure\n")
    result = cli_runner.invoke(main, ["--workspace", str(ws), "--check-config"])
    assert result.exit_code == 1
    assert "Invalid config" in result.output
    assert "clould" in result.output


def test_cli_check_config_invalid_enum(tmp_path):
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text("cloud: digitalocean\n")
    result = cli_runner.invoke(main, ["--workspace", str(ws), "--check-config"])
    assert result.exit_code == 1
    assert "Invalid config" in result.output


def test_cli_check_config_missing(tmp_path):
    ws = _make_workspace(tmp_path)  # no config file present
    result = cli_runner.invoke(main, ["--workspace", str(ws), "--check-config"])
    assert result.exit_code == 2
    assert "No config file found" in result.output


def test_cli_check_config_explicit_path_missing(tmp_path):
    ws = _make_workspace(tmp_path)
    result = cli_runner.invoke(
        main,
        ["--workspace", str(ws), "--config", str(tmp_path / "nope.yaml"), "--check-config"],
    )
    assert result.exit_code == 2
    assert "not found" in result.output


def test_cli_check_config_explicit_path_is_directory(tmp_path):
    """A directory passed as --config is a non-regular file, not 'not found'."""
    ws = _make_workspace(tmp_path)
    a_dir = tmp_path / "cfgdir"
    a_dir.mkdir()
    result = cli_runner.invoke(
        main, ["--workspace", str(ws), "--config", str(a_dir), "--check-config"]
    )
    assert result.exit_code == 2
    assert "not a regular file" in result.output.lower()


def test_cli_check_config_does_not_generate(tmp_path):
    """--check-config validates only; it never writes generated files."""
    ws = _make_workspace(tmp_path)
    cfg = ws / ".bootstrap-iac.yaml"
    cfg.write_text("company: Acme\ncloud: azure\n")
    result = cli_runner.invoke(main, ["--workspace", str(ws), "--check-config"])
    assert result.exit_code == 0
    assert not (ws / ".github").exists()
    assert not (ws / "CLAUDE.md").exists()


def test_cli_save_then_check_config_roundtrip(tmp_path):
    """A saved config passes --check-config (version stamp is accepted)."""
    ws = _make_workspace(tmp_path)
    save = cli_runner.invoke(main, [
        "--workspace", str(ws),
        "--company", "RoundTrip",
        "--cloud", "aws",
        "--orchestration", "terramate",
        "--ci-cd", "github-actions",
        "--target", "both",
        "--non-interactive",
        "--save-config",
    ])
    assert save.exit_code == 0
    cfg = ws / ".bootstrap-iac.yaml"
    assert yaml.safe_load(cfg.read_text())["version"] == "1"

    check = cli_runner.invoke(main, ["--workspace", str(ws), "--check-config"])
    assert check.exit_code == 0
    assert "Config is valid" in check.output
