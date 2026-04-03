"""bootstrap-iac CLI — interactive IaC workspace bootstrapper.

Usage examples::

    # Interactive mode (prompts for all values)
    bootstrap-iac

    # Non-interactive (CI/scripted) mode
    bootstrap-iac --company "Acme Corp" --cloud azure --target both --non-interactive

    # Preview without writing
    bootstrap-iac --dry-run

    # Check existing output for unreplaced placeholders
    bootstrap-iac --validate
    bootstrap-iac --validate /path/to/workspace
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from bootstrap_iac import __version__
from bootstrap_iac.discovery import scan_workspace
from bootstrap_iac.generator import generate_files, get_templates_dir
from bootstrap_iac.interview import build_context, run_interview
from bootstrap_iac.validator import validate_directory, validate_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_header() -> None:
    click.echo()
    click.secho("  bootstrap-iac", bold=True, fg="cyan")
    click.secho(
        "  Bootstrap AI agent customisations for your IaC workspace\n", fg="cyan"
    )


def _print_generated(results: list, dry_run: bool) -> None:
    action = "Would generate" if dry_run else "Generated"
    written = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]

    if written:
        click.secho(f"\n  {action} {len(written)} file(s):", bold=True)
        for r in written:
            click.echo(f"    ✓  {r.output_path}")
    if skipped:
        click.secho(f"\n  Skipped {len(skipped)} existing file(s):", fg="yellow")
        for r in skipped:
            click.echo(f"    –  {r.output_path}  ({r.skip_reason})")


def _print_validation_results(issues: dict) -> int:
    """Print validation results. Returns exit code (0 = clean, 1 = issues)."""
    if not issues:
        click.secho("\n  ✓  No unreplaced placeholders found.", fg="green", bold=True)
        return 0

    total = sum(len(v) for v in issues.values())
    click.secho(
        f"\n  ✗  Found {total} unreplaced placeholder(s) in {len(issues)} file(s):\n",
        fg="red",
        bold=True,
    )
    for file_path, placeholders in sorted(issues.items()):
        click.secho(f"    {file_path}", fg="yellow")
        for ph in placeholders:
            click.echo(f"      • {{{{{ph}}}}}")
    return 1


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

_CLOUD_CHOICES = click.Choice(["azure", "aws", "gcp"], case_sensitive=False)
_TARGET_CHOICES = click.Choice(["copilot", "claude", "both"], case_sensitive=False)
_ORCH_CHOICES = click.Choice(["terragrunt", "terramate", "none"], case_sensitive=False)
_CICD_CHOICES = click.Choice(
    ["github-actions", "azure-devops", "gitlab-ci", "atlantis"],
    case_sensitive=False,
)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
# ---- Core interview options (non-interactive mode) ----
@click.option("--company", metavar="NAME", help="Company / organisation name.")
@click.option(
    "--cloud",
    type=_CLOUD_CHOICES,
    metavar="PROVIDER",
    help="Primary cloud provider: azure | aws | gcp.",
)
@click.option(
    "--module-prefix",
    metavar="PREFIX",
    help="Module directory prefix (e.g. tf-module, terraform-aws).",
)
@click.option(
    "--orchestration",
    type=_ORCH_CHOICES,
    metavar="TOOL",
    help="Orchestration tool: terragrunt | terramate | none.",
)
@click.option(
    "--orchestration-dir",
    metavar="DIR",
    help="Directory containing orchestration configs.",
)
@click.option(
    "--ci-cd",
    type=_CICD_CHOICES,
    metavar="PLATFORM",
    help="CI/CD platform: github-actions | azure-devops | gitlab-ci | atlantis.",
)
@click.option("--auth", metavar="PATTERN", help="Authentication pattern description.")
@click.option("--state-backend", metavar="BACKEND", help="Terraform state backend.")
@click.option("--naming", metavar="PATTERN", help="Resource naming pattern.")
@click.option("--tag-strategy", metavar="STRATEGY", help="Tagging/labelling strategy.")
@click.option("--org", metavar="ORG", help="GitHub/ADO org (used in source URLs).")
# ---- Targeting ----
@click.option(
    "--target",
    type=_TARGET_CHOICES,
    default=None,
    help="Which tool(s) to generate for: copilot | claude | both. [default: both]",
)
# ---- Paths ----
@click.option(
    "--workspace",
    "workspace_dir",
    metavar="PATH",
    default=".",
    show_default=True,
    help="Path to the IaC workspace to scan for defaults.",
)
@click.option(
    "--output-dir",
    metavar="PATH",
    default=None,
    help="Where to write generated files. Defaults to --workspace.",
)
# ---- Behaviour flags ----
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be generated without writing any files.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing files (default: skip).",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Use discovered defaults only — never prompt. Combine with --company, --cloud, etc.",
)
@click.option(
    "--validate",
    "validate_path",
    metavar="PATH",
    is_eager=True,
    default=None,
    help=(
        "Check files in PATH (or --workspace if omitted) for unreplaced "
        "{{PLACEHOLDER}} tokens. Exits 1 if any are found."
    ),
)
def main(
    company: Optional[str],
    cloud: Optional[str],
    module_prefix: Optional[str],
    orchestration: Optional[str],
    orchestration_dir: Optional[str],
    ci_cd: Optional[str],
    auth: Optional[str],
    state_backend: Optional[str],
    naming: Optional[str],
    tag_strategy: Optional[str],
    org: Optional[str],
    target: Optional[str],
    workspace_dir: str,
    output_dir: Optional[str],
    dry_run: bool,
    overwrite: bool,
    non_interactive: bool,
    validate_path: Optional[str],
) -> None:
    """Bootstrap AI agent customisations for a Terraform IaC workspace.

    Runs discover → interview → generate and writes Copilot (.github/) and/or
    Claude Code (CLAUDE.md, .claude/) customisation files into OUTPUT_DIR.

    Run without flags for fully interactive mode.
    """
    _print_header()

    # ------------------------------------------------------------------ #
    # --validate mode                                                      #
    # ------------------------------------------------------------------ #
    if validate_path is not None:
        scan_path = Path(validate_path) if validate_path else Path(workspace_dir)
        click.echo(f"  Scanning {scan_path} for unreplaced placeholders …\n")
        if scan_path.is_file():
            found = validate_file(scan_path)
            issues = {scan_path: found} if found else {}
        else:
            issues = validate_directory(scan_path)
        exit_code = _print_validation_results(issues)
        sys.exit(exit_code)

    # ------------------------------------------------------------------ #
    # Resolve paths                                                        #
    # ------------------------------------------------------------------ #
    ws_path = Path(workspace_dir).resolve()
    out_path = Path(output_dir).resolve() if output_dir else ws_path

    # ------------------------------------------------------------------ #
    # Phase 1: Discovery                                                   #
    # ------------------------------------------------------------------ #
    click.echo(f"  Scanning workspace: {ws_path} …")
    discovery = scan_workspace(ws_path)

    if discovery.notes:
        for note in discovery.notes:
            click.secho(f"  ℹ  {note}", fg="yellow")

    detected_parts = []
    if discovery.cloud_provider:
        detected_parts.append(("Cloud provider", discovery.cloud_provider))
    if discovery.orchestration_tool:
        detected_parts.append(("Orchestration", discovery.orchestration_tool))
    if discovery.ci_cd_platform:
        detected_parts.append(("CI/CD platform", discovery.ci_cd_platform))
    if discovery.module_prefix:
        detected_parts.append(("Module prefix", discovery.module_prefix))
    if discovery.org_name:
        detected_parts.append(("Organisation", discovery.org_name))
    if discovery.naming_pattern:
        detected_parts.append(("Naming pattern", discovery.naming_pattern))
    if discovery.state_backend:
        detected_parts.append(("State backend", discovery.state_backend))
    if discovery.auth_pattern:
        detected_parts.append(("Auth pattern", discovery.auth_pattern))
    if discovery.tag_strategy:
        detected_parts.append(("Tag strategy", discovery.tag_strategy))

    if detected_parts:
        click.echo()
        click.secho("  Auto-detected values:", bold=True)
        for label, value in detected_parts:
            click.echo(f"    • {label}: {value}")
        click.echo()

    # ------------------------------------------------------------------ #
    # Normalise CLI flag values to match interview choices                  #
    # ------------------------------------------------------------------ #
    _cloud_map = {"azure": "Azure", "aws": "AWS", "gcp": "GCP"}
    _orch_map = {
        "terragrunt": "Terragrunt",
        "terramate": "Terramate",
        "none": "None",
    }
    _cicd_map = {
        "github-actions": "GitHub Actions",
        "azure-devops": "Azure DevOps",
        "gitlab-ci": "GitLab CI",
        "atlantis": "Atlantis",
    }

    overrides: dict = {}
    if company:
        overrides["COMPANY_NAME"] = company
    if cloud:
        overrides["CLOUD_PROVIDER"] = _cloud_map.get(cloud.lower(), cloud)
    if module_prefix:
        overrides["MODULE_PREFIX"] = module_prefix
    if orchestration:
        overrides["ORCHESTRATION_TOOL"] = _orch_map.get(orchestration.lower(), orchestration)
    if orchestration_dir:
        overrides["ORCHESTRATION_DIR"] = orchestration_dir
    if ci_cd:
        overrides["CI_CD_PLATFORM"] = _cicd_map.get(ci_cd.lower(), ci_cd)
    if auth:
        overrides["AUTH_PATTERN"] = auth
    if state_backend:
        overrides["STATE_BACKEND"] = state_backend
    if naming:
        overrides["NAMING_PATTERN"] = naming
    if tag_strategy:
        overrides["TAG_STRATEGY"] = tag_strategy
    if org:
        overrides["ORG"] = org
    if target:
        overrides["TARGET"] = target

    # ------------------------------------------------------------------ #
    # Phase 2: Interview                                                    #
    # ------------------------------------------------------------------ #
    if not non_interactive:
        click.echo()

    answers = run_interview(
        discovery,
        non_interactive=non_interactive,
        overrides=overrides,
    )

    resolved_target = answers.get("TARGET", "both")

    # ------------------------------------------------------------------ #
    # Phase 3: Build full context                                           #
    # ------------------------------------------------------------------ #
    context = build_context(answers)

    # ------------------------------------------------------------------ #
    # Phase 4: Generate                                                     #
    # ------------------------------------------------------------------ #
    if dry_run:
        click.secho("\n  Dry run — no files will be written.\n", fg="yellow")
    else:
        click.echo(f"\n  Writing to: {out_path}")

    results = generate_files(
        context,
        out_path,
        target=resolved_target,
        dry_run=dry_run,
        skip_existing=not overwrite,
    )

    _print_generated(results, dry_run)

    # ------------------------------------------------------------------ #
    # Summary                                                               #
    # ------------------------------------------------------------------ #
    click.echo()
    if dry_run:
        click.secho(
            "  Run without --dry-run to write these files.", fg="cyan"
        )
    else:
        written = [r for r in results if not r.skipped]
        if written:
            click.secho(
                "  Bootstrap complete. Review generated files before committing.",
                fg="green",
                bold=True,
            )
            click.echo(
                "  Run `bootstrap-iac --validate` to check for any remaining placeholders."
            )
        else:
            click.secho("  Nothing written.", fg="yellow")
    click.echo()
