"""Integration tests for the bootstrap-iac CLI entry point."""

import pytest
from pathlib import Path

from click.testing import CliRunner

from bootstrap_iac.cli import main


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# --help / --version
# ---------------------------------------------------------------------------


def test_help_flag(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Bootstrap AI agent customisations" in result.output


def test_version_flag(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# --validate
# ---------------------------------------------------------------------------


def test_validate_clean_directory(runner, tmp_path):
    (tmp_path / "clean.md").write_text("No placeholders here.")
    result = runner.invoke(main, ["--validate", str(tmp_path)])
    assert result.exit_code == 0
    assert "No unreplaced placeholders" in result.output


def test_validate_dirty_directory(runner, tmp_path):
    (tmp_path / "dirty.md").write_text("Hello {{COMPANY_NAME}}!")
    result = runner.invoke(main, ["--validate", str(tmp_path)])
    assert result.exit_code == 1
    assert "COMPANY_NAME" in result.output


def test_validate_single_file(runner, tmp_path):
    f = tmp_path / "test.md"
    f.write_text("{{CLOUD_PROVIDER}} is set")
    result = runner.invoke(main, ["--validate", str(f)])
    assert result.exit_code == 1
    assert "CLOUD_PROVIDER" in result.output


# ---------------------------------------------------------------------------
# --dry-run (non-interactive)
# ---------------------------------------------------------------------------


def test_dry_run_no_files_written(runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "--company", "DryRunCo",
            "--cloud", "azure",
            "--target", "both",
            "--non-interactive",
            "--dry-run",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Would generate" in result.output
    # No actual files should be written
    generated = list(tmp_path.rglob("*.md"))
    assert len(generated) == 0


# ---------------------------------------------------------------------------
# Full generation (non-interactive)
# ---------------------------------------------------------------------------


def test_generate_copilot_files(runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "--company", "TestCo",
            "--cloud", "azure",
            "--module-prefix", "tf-module",
            "--orchestration", "none",
            "--ci-cd", "github-actions",
            "--target", "copilot",
            "--non-interactive",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Bootstrap complete" in result.output
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()

    content = (tmp_path / ".github" / "copilot-instructions.md").read_text()
    assert "TestCo" in content


def test_generate_claude_files(runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "--company", "ClaudeCo",
            "--cloud", "aws",
            "--module-prefix", "terraform-aws",
            "--orchestration", "none",
            "--ci-cd", "github-actions",
            "--target", "claude",
            "--non-interactive",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "CLAUDE.md").exists()

    content = (tmp_path / "CLAUDE.md").read_text()
    assert "ClaudeCo" in content


def test_generate_both_targets(runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "--company", "BothCo",
            "--cloud", "azure",
            "--orchestration", "terragrunt",
            "--ci-cd", "github-actions",
            "--target", "both",
            "--non-interactive",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0

    # Both Copilot and Claude files should exist
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()

    # Orchestration-specific files should exist
    assert (tmp_path / ".github" / "agents" / "terragrunt-stack-manager.agent.md").exists()
    assert (tmp_path / ".claude" / "commands" / "create-orchestration-stack.md").exists()


def test_generate_with_overwrite(runner, tmp_path):
    # Create an existing file
    gh = tmp_path / ".github"
    gh.mkdir(parents=True)
    existing = gh / "copilot-instructions.md"
    existing.write_text("# old content")

    result = runner.invoke(
        main,
        [
            "--company", "OverwriteCo",
            "--cloud", "azure",
            "--target", "copilot",
            "--non-interactive",
            "--overwrite",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    content = existing.read_text()
    assert "OverwriteCo" in content
    assert "old content" not in content


def test_generate_skips_existing_by_default(runner, tmp_path):
    gh = tmp_path / ".github"
    gh.mkdir(parents=True)
    existing = gh / "copilot-instructions.md"
    existing.write_text("# existing content")

    result = runner.invoke(
        main,
        [
            "--company", "SkipCo",
            "--cloud", "azure",
            "--target", "copilot",
            "--non-interactive",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Skipped" in result.output
    assert existing.read_text() == "# existing content"


# ---------------------------------------------------------------------------
# Cloud-specific template selection
# ---------------------------------------------------------------------------


def test_aws_uses_cloud_specific_templates(runner, tmp_path):
    """When --cloud aws, cloud-specific templates should be used if available."""
    result = runner.invoke(
        main,
        [
            "--company", "AwsCo",
            "--cloud", "aws",
            "--orchestration", "none",
            "--ci-cd", "github-actions",
            "--target", "copilot",
            "--non-interactive",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()


def test_gcp_uses_cloud_specific_templates(runner, tmp_path):
    """When --cloud gcp, cloud-specific templates should be used if available."""
    result = runner.invoke(
        main,
        [
            "--company", "GcpCo",
            "--cloud", "gcp",
            "--orchestration", "none",
            "--ci-cd", "github-actions",
            "--target", "both",
            "--non-interactive",
            "--workspace", str(tmp_path),
            "--output-dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_invalid_cloud_rejected(runner):
    result = runner.invoke(main, ["--cloud", "invalid"])
    assert result.exit_code != 0


def test_invalid_target_rejected(runner):
    result = runner.invoke(main, ["--target", "invalid"])
    assert result.exit_code != 0
