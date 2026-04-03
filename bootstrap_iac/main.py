"""CLI entry point for bootstrap-iac."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from bootstrap_iac.discover import discover_workspace
from bootstrap_iac.generate import generate_files
from bootstrap_iac.interview import run_interview


@click.command()
@click.option(
    "--cloud",
    type=click.Choice(["aws", "azure", "gcp"], case_sensitive=False),
    default=None,
    help="Cloud provider (skips that interview question).",
)
@click.option(
    "--output-dir",
    default=".",
    show_default=True,
    help="Directory to write generated files into.",
    type=click.Path(file_okay=False, writable=True),
)
@click.option(
    "--tool",
    type=click.Choice(["copilot", "claude", "both"], case_sensitive=False),
    default=None,
    help="Target tool(s) to generate files for (overrides interview question 13).",
)
@click.option(
    "--workspace",
    default=".",
    show_default=True,
    help="IaC workspace directory to scan for existing patterns.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing output files (default: skip them).",
)
@click.option(
    "--non-interactive",
    "non_interactive",
    is_flag=True,
    default=False,
    help="Use defaults for all questions without prompting (useful for CI/testing).",
)
@click.version_option(package_name="bootstrap-iac")
def cli(
    cloud: str | None,
    output_dir: str,
    tool: str | None,
    workspace: str,
    overwrite: bool,
    non_interactive: bool,
) -> None:
    """Bootstrap AI agent customizations for a Terraform IaC workspace.

    Runs through a short interview (discover → interview → generate) and
    writes Copilot and/or Claude Code configuration files into OUTPUT_DIR.

    \b
    Examples:
      bootstrap-iac
      bootstrap-iac --cloud azure --output-dir ~/my-iac-workspace
      bootstrap-iac --cloud aws --tool copilot --non-interactive
    """
    click.echo(click.style("🚀  bootstrap-iac", bold=True, fg="cyan"))
    click.echo("Generates AI agent customizations for your Terraform IaC workspace.\n")

    # ------------------------------------------------------------------ #
    # Phase 1: Discovery
    # ------------------------------------------------------------------ #
    workspace_path = Path(workspace).resolve()
    click.echo(f"📂  Scanning workspace: {workspace_path}")

    workspace_profile = discover_workspace(workspace_path)
    _report_discovery(workspace_profile)

    # ------------------------------------------------------------------ #
    # Phase 2: Interview
    # ------------------------------------------------------------------ #
    click.echo("\n📋  Interview — answer a few questions about your workspace.")
    click.echo("    (Press Enter to accept defaults shown in [brackets].)\n")

    answers = run_interview(
        cloud_flag=cloud,
        non_interactive=non_interactive,
        workspace_profile=workspace_profile,
    )

    # --tool flag overrides question 13 (target tools)
    if tool:
        answers["target_tools"] = tool

    # ------------------------------------------------------------------ #
    # Phase 3: Generate
    # ------------------------------------------------------------------ #
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    click.echo(f"\n⚙️   Generating files into: {output_path}")

    try:
        written, skipped = generate_files(answers, output_path, overwrite=overwrite)
    except FileNotFoundError as exc:
        click.echo(click.style(f"\n❌  Error: {exc}", fg="red"), err=True)
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    click.echo()
    if written:
        click.echo(click.style(f"✅  {len(written)} file(s) written:", fg="green"))
        for path in written:
            rel = _relative_to_or_abs(path, output_path)
            click.echo(f"    {rel}")

    if skipped:
        click.echo(
            click.style(f"\n⏭️   {len(skipped)} file(s) skipped (already exist):", fg="yellow")
        )
        for path in skipped:
            rel = _relative_to_or_abs(path, output_path)
            click.echo(f"    {rel}")
        click.echo("    Re-run with --overwrite to replace them.")

    if not written and not skipped:
        click.echo(click.style("⚠️   No files were generated.", fg="yellow"))

    click.echo(
        "\n💡  Next steps:\n"
        "    1. Review generated files and fill in any remaining TODO comments.\n"
        "    2. For Copilot: commit .github/ files to the workspace repo.\n"
        "    3. For Claude Code: commit CLAUDE.md and .claude/ to the workspace repo."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report_discovery(profile: dict) -> None:
    """Print a brief discovery summary."""
    found = []
    if profile["has_terraform"]:
        found.append("Terraform (.tf files)")
    if profile["has_terragrunt"]:
        found.append("Terragrunt (terragrunt.hcl)")
    if profile["has_terramate"]:
        found.append("Terramate (.tm.hcl)")
    if profile["has_github_actions"]:
        found.append("GitHub Actions")
    if profile["has_azure_devops"]:
        found.append("Azure DevOps pipelines")
    if profile["has_gitlab_ci"]:
        found.append("GitLab CI")
    if profile["has_atlantis"]:
        found.append("Atlantis")
    if profile["has_copilot"]:
        found.append(click.style("existing Copilot config", fg="yellow"))
    if profile["has_claude"]:
        found.append(click.style("existing Claude config", fg="yellow"))

    if found:
        click.echo("    Found: " + ", ".join(found))
    else:
        click.echo("    Nothing detected — will use defaults from the interview.")


def _relative_to_or_abs(path: Path, base: Path) -> str:
    """Return path relative to base, or absolute if it's not under base."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)
