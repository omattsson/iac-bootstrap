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

import json
import os
import stat
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from bootstrap_iac import __version__
from bootstrap_iac.config import (
    CICD_MAP,
    CLOUD_MAP,
    CONFIG_FILENAMES,
    ORCH_MAP,
    config_key_for,
    find_config,
    load_config,
    write_config,
)
from bootstrap_iac.discovery import scan_workspace
from bootstrap_iac.generator import GenerationError, generate_files, get_templates_dir
from bootstrap_iac.interview import build_context, run_interview
from bootstrap_iac.validator import (
    DirectoryReport,
    ValidationReadError,
    validate_directory,
    validate_file,
)


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


def _print_validation_results(report: DirectoryReport) -> int:
    """Print a validation report.

    Returns an exit code: 0 when clean, 1 when placeholders were found, and 2
    when any file could not be read (a read error outranks a plain finding).
    """
    if report.ok:
        click.secho("\n  ✓  No unreplaced placeholders found.", fg="green", bold=True)
        return 0

    if report.placeholders:
        total = sum(len(v) for v in report.placeholders.values())
        click.secho(
            f"\n  ✗  Found {total} unreplaced placeholder(s) in "
            f"{len(report.placeholders)} file(s):\n",
            fg="red",
            bold=True,
        )
        for file_path, placeholders in sorted(report.placeholders.items()):
            click.secho(f"    {file_path}", fg="yellow")
            for ph in placeholders:
                click.echo(f"      • {{{{{ph}}}}}")

    if report.read_errors:
        click.secho(
            f"\n  ✗  Could not read {len(report.read_errors)} path(s):\n",
            fg="red",
            bold=True,
            err=True,
        )
        for file_path, reason in sorted(report.read_errors.items()):
            click.secho(f"    {file_path}: {reason}", fg="yellow", err=True)

    return 2 if report.read_errors else 1


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

_CLOUD_CHOICES = click.Choice(list(CLOUD_MAP), case_sensitive=False)
_TARGET_CHOICES = click.Choice(["copilot", "claude", "both"], case_sensitive=False)
_ORCH_CHOICES = click.Choice(list(ORCH_MAP), case_sensitive=False)
_CICD_CHOICES = click.Choice(list(CICD_MAP), case_sensitive=False)


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
    help="Orchestration tool: terragrunt | terramate | pulumi | none.",
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
    help="Overwrite existing files and config (default: skip).",
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
    is_flag=False,
    flag_value="",
    is_eager=True,
    default=None,
    help=(
        "Check files in PATH (or --workspace if omitted) for unreplaced "
        "{{PLACEHOLDER}} tokens. Exits 1 if any are found, or 2 if the path is "
        "missing or unreadable."
    ),
)
@click.option(
    "--config",
    "config_path",
    metavar="PATH",
    default=None,
    help=(
        "Path to a .bootstrap-iac.yaml config file. "
        "Auto-detected in workspace root if not specified."
    ),
)
@click.option(
    "--save-config",
    is_flag=True,
    default=False,
    help=(
        "Write interview answers after generation. Saves back to --config PATH "
        "when provided; otherwise writes .bootstrap-iac.yaml in the workspace."
    ),
)
@click.option(
    "--check-config",
    is_flag=True,
    default=False,
    help=(
        "Validate the config file (--config PATH, or the one auto-detected in "
        "--workspace) and exit without generating. Exits 0 if valid, 1 if the "
        "config is invalid, 2 if it is missing or unreadable."
    ),
)
@click.option(
    "--discover",
    is_flag=True,
    default=False,
    help=(
        "Scan --workspace and print the discovery result as JSON (including "
        "evidence for each inferred value), then exit without generating."
    ),
)
@click.option(
    "--ignore-dir",
    "ignore_dirs",
    metavar="DIR",
    multiple=True,
    help=(
        "Directory name to skip during workspace discovery, in addition to the "
        "built-in ignore list. Repeat for multiple directories."
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
    config_path: Optional[str],
    save_config: bool,
    check_config: bool,
    discover: bool,
    ignore_dirs: tuple[str, ...],
) -> None:
    """Bootstrap AI agent customisations for a Terraform IaC workspace.

    Runs discover → interview → generate and writes Copilot (.github/) and/or
    Claude Code (CLAUDE.md, .claude/) customisation files into OUTPUT_DIR.

    Run without flags for fully interactive mode.
    """
    # --discover emits machine-readable JSON on stdout, so it prints no banner.
    if not discover:
        _print_header()

    # ------------------------------------------------------------------ #
    # --validate mode                                                      #
    # ------------------------------------------------------------------ #
    if validate_path is not None:
        scan_path = Path(validate_path) if validate_path else Path(workspace_dir)
        click.echo(f"  Scanning {scan_path} for unreplaced placeholders …\n")
        # Stat once, so a missing path and an unreadable path are told apart
        # reliably. os.stat raises for both, unlike Path.exists()/is_file(),
        # which suppress most OS errors and would report an unreadable path as
        # a clean scan.
        try:
            st = os.stat(scan_path)
        except FileNotFoundError as exc:
            click.secho(
                f"  ✗  Path not found: {scan_path}: {exc.strerror or exc}",
                fg="red",
                bold=True,
                err=True,
            )
            sys.exit(2)
        except OSError as exc:
            click.secho(
                f"  ✗  Could not access {scan_path}: {exc.strerror or exc}",
                fg="red",
                bold=True,
                err=True,
            )
            sys.exit(2)

        if stat.S_ISDIR(st.st_mode):
            report = validate_directory(scan_path)
        elif not stat.S_ISREG(st.st_mode):
            # Not a directory and not a regular file (for example a FIFO,
            # socket, or device). There is nothing to validate, and reading
            # some of these would block, so refuse it explicitly.
            click.secho(
                f"  ✗  Not a regular file: {scan_path}",
                fg="red",
                bold=True,
                err=True,
            )
            sys.exit(2)
        else:
            try:
                found = validate_file(scan_path)
            except ValidationReadError as exc:
                click.secho(
                    f"  ✗  Could not read {scan_path}: {exc.reason}",
                    fg="red",
                    bold=True,
                    err=True,
                )
                sys.exit(2)
            except OSError as exc:
                click.secho(
                    f"  ✗  Could not read {scan_path}: {exc.strerror or exc}",
                    fg="red",
                    bold=True,
                    err=True,
                )
                sys.exit(2)
            report = DirectoryReport(
                placeholders={scan_path: found} if found else {}
            )
        exit_code = _print_validation_results(report)
        sys.exit(exit_code)

    # ------------------------------------------------------------------ #
    # --check-config mode: validate a config file and exit.               #
    # ------------------------------------------------------------------ #
    if check_config:
        ws_path = Path(workspace_dir).resolve()
        if config_path:
            cfg_file = Path(config_path).resolve()
            # Stat once so missing, unreadable, and non-regular paths are told
            # apart, instead of is_file() reporting all three as "not found".
            try:
                cfg_stat = os.stat(cfg_file)
            except FileNotFoundError:
                click.secho(
                    f"  ✗  Config file not found: {cfg_file}",
                    fg="red",
                    bold=True,
                    err=True,
                )
                sys.exit(2)
            except OSError as exc:
                click.secho(
                    f"  ✗  Could not access config file {cfg_file}: "
                    f"{exc.strerror or exc}",
                    fg="red",
                    bold=True,
                    err=True,
                )
                sys.exit(2)
            if not stat.S_ISREG(cfg_stat.st_mode):
                click.secho(
                    f"  ✗  Config path is not a regular file: {cfg_file}",
                    fg="red",
                    bold=True,
                    err=True,
                )
                sys.exit(2)
        else:
            cfg_file = find_config(ws_path)
            if not cfg_file:
                click.secho(
                    f"  ✗  No config file found in {ws_path} "
                    f"({' or '.join(CONFIG_FILENAMES)}).",
                    fg="red",
                    bold=True,
                    err=True,
                )
                sys.exit(2)

        click.echo(f"  Checking config: {cfg_file}")
        try:
            overrides = load_config(cfg_file)
        except (yaml.YAMLError, ValueError) as exc:
            click.secho(f"  ✗  Invalid config: {exc}", fg="red", bold=True, err=True)
            sys.exit(1)
        except OSError as exc:
            click.secho(
                f"  ✗  Unable to read config: {exc}", fg="red", bold=True, err=True
            )
            sys.exit(2)

        click.secho("\n  ✓  Config is valid.", fg="green", bold=True)
        if overrides:
            click.echo("\n  Resolved values:")
            for upper_key in sorted(overrides, key=config_key_for):
                click.echo(f"    {config_key_for(upper_key)} = {overrides[upper_key]}")
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # --discover mode: print the discovery result as JSON and exit.       #
    # ------------------------------------------------------------------ #
    if discover:
        ws_path = Path(workspace_dir).resolve()
        discovery = scan_workspace(ws_path, ignored_dirs=list(ignore_dirs) or None)
        click.echo(json.dumps(discovery.to_dict(), indent=2))
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # Resolve paths                                                        #
    # ------------------------------------------------------------------ #
    ws_path = Path(workspace_dir).resolve()
    out_path = Path(output_dir).resolve() if output_dir else ws_path

    # ------------------------------------------------------------------ #
    # Load config file (defaults that CLI flags override)                   #
    # ------------------------------------------------------------------ #
    config_defaults: dict = {}
    if config_path:
        cfg_file = Path(config_path).resolve()
        if not cfg_file.is_file():
            click.secho(f"  ✗  Config file not found: {cfg_file}", fg="red")
            sys.exit(1)
    else:
        cfg_file = find_config(ws_path)

    if cfg_file:
        click.echo(f"  Loading config: {cfg_file}")
        try:
            config_defaults = load_config(cfg_file)
        except (yaml.YAMLError, ValueError) as exc:
            click.secho(f"  ✗  Invalid config file: {exc}", fg="red")
            sys.exit(1)
        except OSError as exc:
            click.secho(f"  ✗  Unable to read config file: {exc}", fg="red")
            sys.exit(1)

    # ------------------------------------------------------------------ #
    # Phase 1: Discovery                                                   #
    # ------------------------------------------------------------------ #
    click.echo(f"  Scanning workspace: {ws_path} …")
    discovery = scan_workspace(ws_path, ignored_dirs=list(ignore_dirs) or None)

    if discovery.notes:
        for note in discovery.notes:
            click.secho(f"  ℹ  {note}", fg="yellow")

    detected_parts = []
    if discovery.cloud_provider:
        detected_parts.append(f"cloud={discovery.cloud_provider}")
    if discovery.orchestration_tool:
        detected_parts.append(f"orchestration={discovery.orchestration_tool}")
    if discovery.ci_cd_platform:
        detected_parts.append(f"ci_cd={discovery.ci_cd_platform}")
    if discovery.module_prefix:
        detected_parts.append(f"module_prefix={discovery.module_prefix}")
    if discovery.org_name:
        detected_parts.append(f"org={discovery.org_name}")
    if discovery.state_backend:
        detected_parts.append(f"state_backend={discovery.state_backend}")
    if discovery.naming_pattern:
        detected_parts.append(f"naming={discovery.naming_pattern}")
    if detected_parts:
        click.echo(f"  Detected: {', '.join(detected_parts)}")

    # ------------------------------------------------------------------ #
    # Normalise CLI flag values to match interview choices                  #
    # ------------------------------------------------------------------ #
    overrides: dict = {}
    # Start with config file values as a base layer
    overrides.update(config_defaults)
    # CLI flags override config file values
    if company:
        overrides["COMPANY_NAME"] = company
    if cloud:
        overrides["CLOUD_PROVIDER"] = CLOUD_MAP.get(cloud.lower(), cloud)
    if module_prefix:
        overrides["MODULE_PREFIX"] = module_prefix
    if orchestration:
        overrides["ORCHESTRATION_TOOL"] = ORCH_MAP.get(orchestration.lower(), orchestration)
    if orchestration_dir:
        overrides["ORCHESTRATION_DIR"] = orchestration_dir
    if ci_cd:
        overrides["CI_CD_PLATFORM"] = CICD_MAP.get(ci_cd.lower(), ci_cd)
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

    try:
        results = generate_files(
            context,
            out_path,
            target=resolved_target,
            dry_run=dry_run,
            skip_existing=not overwrite,
        )
    except GenerationError as exc:
        click.secho(f"\n  ✗  {exc}", fg="red", err=True)
        sys.exit(1)

    _print_generated(results, dry_run)

    # ------------------------------------------------------------------ #
    # --save-config: write answers to config file.                         #
    # The global --overwrite flag also applies to the saved config file.   #
    # ------------------------------------------------------------------ #
    if save_config and not dry_run:
        config_out = cfg_file if cfg_file else (ws_path / ".bootstrap-iac.yaml")
        if config_out.exists() and not overwrite:
            click.secho(
                f"  \u2717  Refusing to overwrite existing config: {config_out}. "
                "Re-run with --overwrite to replace it; this flag "
                "applies to both generated files and the saved config.",
                fg="red",
            )
        else:
            write_config(answers, config_out)
            click.echo(f"  Saved config: {config_out}")

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
