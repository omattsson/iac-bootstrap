"""Integration tests for the bootstrap-iac CLI entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
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


def test_validate_missing_path(tmp_path):
    """A typo'd / missing path must fail, not report a clean scan."""
    missing = tmp_path / "does_not_exist"
    result = runner.invoke(main, ["--validate", str(missing)])
    assert result.exit_code == 2
    assert "No unreplaced placeholders" not in result.output
    assert str(missing) in result.output


def test_validate_binary_file_ignored(tmp_path):
    """An explicitly requested unsupported file stays ignored (clean, exit 0)."""
    f = tmp_path / "artifact.bin"
    f.write_bytes(b"\x00\x01{{NOT_SCANNED}}")
    result = runner.invoke(main, ["--validate", str(f)])
    assert result.exit_code == 0
    assert "No unreplaced placeholders" in result.output


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX file permissions not enforced for root or on Windows",
)
def test_validate_unreadable_file(tmp_path):
    f = tmp_path / "locked.md"
    f.write_text("{{COMPANY_NAME}}")
    f.chmod(0o000)
    try:
        result = runner.invoke(main, ["--validate", str(f)])
        assert result.exit_code == 2
        assert str(f) in result.output
    finally:
        f.chmod(0o644)


@pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="named pipes need a POSIX platform"
)
def test_validate_fifo_is_refused(tmp_path):
    """A FIFO with a supported extension is refused, not read (would block).

    Run in a subprocess with a timeout so a regression that let the CLI read
    the FIFO fails the test instead of hanging the whole suite.
    """
    fifo = tmp_path / "pipe.md"
    os.mkfifo(fifo)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bootstrap_iac", "--validate", str(fifo)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 2
        assert "Not a regular file" in (proc.stdout + proc.stderr)
    finally:
        fifo.unlink()


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX file permissions not enforced for root or on Windows",
)
def test_validate_unreadable_parent_reports_access_error(tmp_path):
    """A path under an untraversable dir is an access error, not 'not found'."""
    locked_dir = tmp_path / "locked_dir"
    locked_dir.mkdir()
    target = locked_dir / "file.md"
    target.write_text("{{COMPANY_NAME}}")
    locked_dir.chmod(0o000)
    try:
        result = runner.invoke(main, ["--validate", str(target)])
        assert result.exit_code == 2
        assert "Could not access" in result.output
        assert "not found" not in result.output.lower()
    finally:
        locked_dir.chmod(0o755)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX file permissions not enforced for root or on Windows",
)
def test_validate_directory_with_read_error(tmp_path):
    """A directory scan lists placeholders and still exits 2 on a read error."""
    (tmp_path / "dirty.md").write_text("Company: {{COMPANY_NAME}}\n")
    locked = tmp_path / "locked.md"
    locked.write_text("Provider: {{CLOUD_PROVIDER}}\n")
    locked.chmod(0o000)
    try:
        result = runner.invoke(main, ["--validate", str(tmp_path)])
        assert result.exit_code == 2
        assert "COMPANY_NAME" in result.output
        assert "Could not read" in result.output
        assert "locked.md" in result.output
    finally:
        locked.chmod(0o644)


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
