"""Integration tests for the bootstrap-iac CLI entry point."""

from __future__ import annotations

import textwrap
from pathlib import Path

from click.testing import CliRunner

from bootstrap_iac import __version__
from bootstrap_iac.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

runner = CliRunner()


def _make_workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with a provider block."""
    (tmp_path / "main.tf").write_text('provider "azurerm" {\n  features {}\n}\n')
    return tmp_path


# ---------------------------------------------------------------------------
# --help / --version
# ---------------------------------------------------------------------------


def test_help_flag():
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "bootstrap-iac" in result.output.lower() or "Bootstrap" in result.output


def test_version_flag():
    result = runner.invoke(main, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.output


# ---------------------------------------------------------------------------
# --validate
# ---------------------------------------------------------------------------


def test_validate_clean_directory(tmp_path):
    (tmp_path / "README.md").write_text("Hello, no placeholders here.\n")
    result = runner.invoke(main, ["--validate", str(tmp_path)])
    assert result.exit_code == 0
    assert "No unreplaced placeholders" in result.output


def test_validate_dirty_directory(tmp_path):
    (tmp_path / "copilot-instructions.md").write_text(
        "Company: {{COMPANY_NAME}}\n"
    )
    result = runner.invoke(main, ["--validate", str(tmp_path)])
    assert result.exit_code == 1
    assert "COMPANY_NAME" in result.output


def test_validate_single_file(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("Provider: {{CLOUD_PROVIDER}}\n")
    result = runner.invoke(main, ["--validate", str(f)])
    assert result.exit_code == 1
    assert "CLOUD_PROVIDER" in result.output


# ---------------------------------------------------------------------------
# --dry-run + --non-interactive
# ---------------------------------------------------------------------------


def test_dry_run_non_interactive(tmp_path):
    ws = _make_workspace(tmp_path)
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--cloud", "azure",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Dry run" in result.output or "dry run" in result.output.lower()
    assert "Would generate" in result.output
    # No files should be written
    assert not (ws / ".github").exists()
    assert not (ws / "CLAUDE.md").exists()


def test_dry_run_copilot_target(tmp_path):
    ws = _make_workspace(tmp_path)
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--cloud", "azure",
            "--target", "copilot",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would generate" in result.output
    # Should list copilot files but not claude
    assert "copilot-instructions.md" in result.output
    assert "CLAUDE.md" not in result.output


def test_dry_run_claude_target(tmp_path):
    ws = _make_workspace(tmp_path)
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--cloud", "azure",
            "--target", "claude",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would generate" in result.output
    assert "CLAUDE.md" in result.output


# ---------------------------------------------------------------------------
# Full generation (non-interactive)
# ---------------------------------------------------------------------------


def test_generate_writes_files(tmp_path):
    ws = _make_workspace(tmp_path)
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "Acme",
            "--cloud", "azure",
            "--non-interactive",
        ],
    )
    assert result.exit_code == 0
    assert "Bootstrap complete" in result.output

    # Copilot files
    assert (ws / ".github" / "copilot-instructions.md").exists()
    instructions = (ws / ".github" / "copilot-instructions.md").read_text()
    assert "Acme" in instructions

    # Claude files
    assert (ws / "CLAUDE.md").exists()
    claude = (ws / "CLAUDE.md").read_text()
    assert "Acme" in claude


def test_generate_skips_existing(tmp_path):
    ws = _make_workspace(tmp_path)
    # Pre-create a copilot instructions file
    gh_dir = ws / ".github"
    gh_dir.mkdir()
    existing = gh_dir / "copilot-instructions.md"
    existing.write_text("original content")

    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "Acme",
            "--cloud", "azure",
            "--non-interactive",
        ],
    )
    assert result.exit_code == 0
    assert "Skipped" in result.output
    # File should remain unchanged
    assert existing.read_text() == "original content"


def test_generate_overwrite(tmp_path):
    ws = _make_workspace(tmp_path)
    gh_dir = ws / ".github"
    gh_dir.mkdir()
    existing = gh_dir / "copilot-instructions.md"
    existing.write_text("original content")

    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "Acme",
            "--cloud", "azure",
            "--non-interactive",
            "--overwrite",
        ],
    )
    assert result.exit_code == 0
    # File should be overwritten with generated content
    assert existing.read_text() != "original content"
    assert "Acme" in existing.read_text()


def test_generate_output_dir(tmp_path):
    ws = _make_workspace(tmp_path)
    out = tmp_path / "output"
    out.mkdir()

    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--output-dir", str(out),
            "--company", "Acme",
            "--cloud", "azure",
            "--non-interactive",
        ],
    )
    assert result.exit_code == 0
    assert (out / ".github" / "copilot-instructions.md").exists()
    assert (out / "CLAUDE.md").exists()
    # Original workspace should NOT have generated files
    assert not (ws / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# Cloud and orchestration flag variations
# ---------------------------------------------------------------------------


def test_generate_aws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--cloud", "aws",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would generate" in result.output


def test_generate_gcp(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--cloud", "gcp",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would generate" in result.output


def test_generate_with_orchestration(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--cloud", "azure",
            "--orchestration", "terragrunt",
            "--orchestration-dir", "infra",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would generate" in result.output


def test_generate_with_pulumi(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--cloud", "azure",
            "--orchestration", "pulumi",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Would generate" in result.output


# ---------------------------------------------------------------------------
# Discovery integration
# ---------------------------------------------------------------------------


def test_discovery_detects_cloud(tmp_path):
    ws = _make_workspace(tmp_path)
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "cloud=Azure" in result.output


def test_discovery_detects_github_actions(tmp_path):
    ws = _make_workspace(tmp_path)
    (ws / ".github" / "workflows").mkdir(parents=True)
    (ws / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")
    result = runner.invoke(
        main,
        [
            "--workspace", str(ws),
            "--company", "TestCo",
            "--non-interactive",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "ci_cd=GitHub Actions" in result.output
