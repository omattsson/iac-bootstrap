"""Tests for the CLI entry point (bootstrap_iac.main)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from bootstrap_iac.main import cli


class TestCliBasic:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "bootstrap-iac" in result.output.lower() or "bootstrap" in result.output.lower()

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_non_interactive_azure(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--cloud", "azure",
                "--output-dir", str(tmp_path),
                "--non-interactive",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".github" / "copilot-instructions.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_non_interactive_aws(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--cloud", "aws",
                "--output-dir", str(tmp_path),
                "--non-interactive",
                "--tool", "copilot",
            ],
        )
        assert result.exit_code == 0, result.output
        instructions = (tmp_path / ".github" / "copilot-instructions.md").read_text()
        assert "AWS" in instructions

    def test_non_interactive_gcp(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--cloud", "gcp",
                "--output-dir", str(tmp_path),
                "--non-interactive",
                "--tool", "claude",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "CLAUDE.md").exists()
        claude = (tmp_path / "CLAUDE.md").read_text()
        assert "GCP" in claude

    def test_tool_copilot_only(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--cloud", "azure",
                "--output-dir", str(tmp_path),
                "--non-interactive",
                "--tool", "copilot",
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / ".github" / "copilot-instructions.md").exists()
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_tool_claude_only(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--cloud", "azure",
                "--output-dir", str(tmp_path),
                "--non-interactive",
                "--tool", "claude",
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "CLAUDE.md").exists()
        assert not (tmp_path / ".github" / "copilot-instructions.md").exists()

    def test_overwrite_flag(self, tmp_path):
        runner = CliRunner()
        # First run
        runner.invoke(
            cli,
            ["--cloud", "azure", "--output-dir", str(tmp_path), "--non-interactive", "--tool", "claude"],
        )
        original = (tmp_path / "CLAUDE.md").read_text()

        # Second run without --overwrite: file unchanged, reported as skipped
        result2 = runner.invoke(
            cli,
            ["--cloud", "azure", "--output-dir", str(tmp_path), "--non-interactive", "--tool", "claude"],
        )
        assert result2.exit_code == 0
        assert "skipped" in result2.output.lower()
        assert (tmp_path / "CLAUDE.md").read_text() == original

        # Third run with --overwrite: file regenerated
        result3 = runner.invoke(
            cli,
            [
                "--cloud", "azure",
                "--output-dir", str(tmp_path),
                "--non-interactive",
                "--tool", "claude",
                "--overwrite",
            ],
        )
        assert result3.exit_code == 0
        assert "skipped" not in result3.output.lower() or "0 file" in result3.output.lower()

    def test_no_unreplaced_placeholders_in_output(self, tmp_path):
        """All {{PLACEHOLDER}} tokens must be replaced in generated output."""
        import re
        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "--cloud", "azure",
                "--output-dir", str(tmp_path),
                "--non-interactive",
            ],
        )
        placeholder_re = re.compile(r"\{\{[A-Z_]+\}\}")
        for output_file in tmp_path.rglob("*.md"):
            content = output_file.read_text()
            matches = placeholder_re.findall(content)
            assert not matches, (
                f"Unreplaced placeholders in {output_file.relative_to(tmp_path)}: {matches}"
            )
