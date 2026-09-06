"""Template engine and file generation.

Reads ``*.tmpl`` files from the bundled ``templates/`` directory, replaces all
``{{PLACEHOLDER}}`` tokens with values from *context*, and writes the results
to an output directory.
"""

from __future__ import annotations

import re
import stat
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


class GenerationError(RuntimeError):
    """Raised when generated output cannot be safely prepared or published."""


# ---------------------------------------------------------------------------
# Templates directory discovery
# ---------------------------------------------------------------------------


def get_templates_dir() -> Path:
    """Locate the bundled templates directory.

    Search order:
    1. ``BOOTSTRAP_IAC_TEMPLATES_DIR`` environment variable.
    2. ``templates/`` sub-directory next to this module file (installed package).
    3. ``references/`` two levels above this file (development checkout).
    """
    import os

    env_dir = os.environ.get("BOOTSTRAP_IAC_TEMPLATES_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p
        raise FileNotFoundError(
            f"BOOTSTRAP_IAC_TEMPLATES_DIR={env_dir!r} does not exist"
        )

    # Installed package: templates/ bundled next to this module
    pkg_dir = Path(__file__).parent
    bundled = pkg_dir / "templates"
    if bundled.is_dir():
        return bundled

    # Development checkout: references/ at repo root
    dev_path = pkg_dir.parent.parent / "references"
    if dev_path.is_dir():
        return dev_path

    raise FileNotFoundError(
        "Cannot locate templates. "
        "Set the BOOTSTRAP_IAC_TEMPLATES_DIR environment variable to the "
        "path of the templates/references directory."
    )


# ---------------------------------------------------------------------------
# Core template engine
# ---------------------------------------------------------------------------


def resolve_placeholders(content: str, context: dict) -> str:
    """Replace every ``{{KEY}}`` token in *content* with ``context[KEY]``.

    Unknown placeholders are left unchanged so the caller can detect them.
    """

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return str(context[key]) if key in context else match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, content)


# ---------------------------------------------------------------------------
# Output-file mapping
# ---------------------------------------------------------------------------


@dataclass
class OutputSpec:
    """Describes a single file to generate."""

    template_rel: str  # relative path within templates dir (e.g. copilot/...)
    output_rel: str  # relative path within output dir
    target: str  # "copilot" | "claude"
    skip_when_no_orchestration: bool = False


def _cloud_template(base_path: str, cloud: str, templates_dir: Path) -> str:
    """Return a cloud-specific template path if it exists, else the base path.

    For example, given ``copilot/copilot-instructions.md.tmpl`` and cloud
    ``aws``, check ``copilot/aws/copilot-instructions.md.tmpl`` first.
    """
    parts = base_path.split("/", 1)
    if len(parts) == 2 and cloud in ("aws", "gcp"):
        cloud_path = f"{parts[0]}/{cloud}/{parts[1]}"
        if (templates_dir / cloud_path).exists():
            return cloud_path
    return base_path


def _build_output_specs(context: dict, templates_dir: Path) -> list[OutputSpec]:
    """Return the list of files to generate based on *context*."""
    orch = context.get("ORCHESTRATION_TOOL", "None")
    orch_lower = context.get("ORCHESTRATION_TOOL_LOWER", "terraform")
    has_orchestration = orch != "None"
    cloud = context.get("CLOUD_PROVIDER", "Azure").lower()

    def _cp(base: str) -> str:
        return _cloud_template(base, cloud, templates_dir)

    specs: list[OutputSpec] = []

    # ---- Copilot outputs ----
    specs += [
        OutputSpec(
            _cp("copilot/copilot-instructions.md.tmpl"),
            ".github/copilot-instructions.md",
            "copilot",
        ),
        OutputSpec(
            "copilot/agents/infra-architect.agent.md.tmpl",
            ".github/agents/infra-architect.agent.md",
            "copilot",
        ),
        OutputSpec(
            _cp("copilot/agents/terraform-module-builder.agent.md.tmpl"),
            ".github/agents/terraform-module-builder.agent.md",
            "copilot",
        ),
        OutputSpec(
            "copilot/agents/terraform-test-writer.agent.md.tmpl",
            ".github/agents/terraform-test-writer.agent.md",
            "copilot",
        ),
        OutputSpec(
            _cp("copilot/skills/create-terraform-module.skill.md.tmpl"),
            ".github/skills/create-terraform-module/SKILL.md",
            "copilot",
        ),
        OutputSpec(
            "copilot/skills/create-infra-pipeline.skill.md.tmpl",
            ".github/skills/create-infra-pipeline/SKILL.md",
            "copilot",
        ),
        OutputSpec(
            _cp("copilot/instructions/terraform-modules.instructions.md.tmpl"),
            ".github/instructions/terraform-modules.instructions.md",
            "copilot",
        ),
        OutputSpec(
            _cp("copilot/instructions/terraform-tests.instructions.md.tmpl"),
            ".github/instructions/terraform-tests.instructions.md",
            "copilot",
        ),
        OutputSpec(
            "copilot/instructions/pipeline-templates.instructions.md.tmpl",
            ".github/instructions/pipeline-templates.instructions.md",
            "copilot",
        ),
        OutputSpec(
            "copilot/instructions/iac-best-practices.instructions.md.tmpl",
            ".github/instructions/iac-best-practices.instructions.md",
            "copilot",
        ),
    ]

    # ---- Orchestration-specific outputs ----
    if has_orchestration:
        # Prefer tool-specific agent/skill/instruction if available
        if orch == "Terramate":
            agent_tmpl = "copilot/agents/terramate-stack-manager.agent.md.tmpl"
            skill_tmpl = "copilot/skills/create-terramate-stack.skill.md.tmpl"
            instr_tmpl = "copilot/instructions/terramate-configs.instructions.md.tmpl"
            claude_tmpl = "claude/commands/create-terramate-stack.md.tmpl"
        elif orch == "Pulumi":
            agent_tmpl = "copilot/agents/pulumi-stack-manager.agent.md.tmpl"
            skill_tmpl = "copilot/skills/create-pulumi-stack.skill.md.tmpl"
            instr_tmpl = "copilot/instructions/pulumi-configs.instructions.md.tmpl"
            claude_tmpl = "claude/commands/create-pulumi-stack.md.tmpl"
        else:
            agent_tmpl = "copilot/agents/orchestration-stack-manager.agent.md.tmpl"
            skill_tmpl = "copilot/skills/create-orchestration-stack.skill.md.tmpl"
            instr_tmpl = "copilot/instructions/orchestration-configs.instructions.md.tmpl"
            claude_tmpl = "claude/commands/create-orchestration-stack.md.tmpl"

        specs += [
            OutputSpec(
                agent_tmpl,
                f".github/agents/{orch_lower}-stack-manager.agent.md",
                "copilot",
            ),
            OutputSpec(
                skill_tmpl,
                f".github/skills/create-{orch_lower}-stack/SKILL.md",
                "copilot",
            ),
            OutputSpec(
                instr_tmpl,
                f".github/instructions/{orch_lower}-configs.instructions.md",
                "copilot",
            ),
        ]

    # ---- Claude Code outputs ----
    specs += [
        OutputSpec(
            _cp("claude/CLAUDE.md.tmpl"),
            "CLAUDE.md",
            "claude",
        ),
        OutputSpec(
            _cp("claude/commands/create-terraform-module.md.tmpl"),
            ".claude/commands/create-terraform-module.md",
            "claude",
        ),
        OutputSpec(
            "claude/commands/create-infra-pipeline.md.tmpl",
            ".claude/commands/create-infra-pipeline.md",
            "claude",
        ),
    ]

    if has_orchestration:
        specs.append(
            OutputSpec(
                claude_tmpl,
                f".claude/commands/create-{orch_lower}-stack.md",
                "claude",
            )
        )

    return specs


# ---------------------------------------------------------------------------
# Generated-file result type
# ---------------------------------------------------------------------------


@dataclass
class GeneratedFile:
    """Represents a file that was (or would be) generated."""

    output_path: Path
    template_path: Path
    content: str
    skipped: bool = False  # True when the file already exists and skip_existing=True
    skip_reason: str = ""


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------


def generate_files(
    context: dict,
    output_dir: Path,
    *,
    target: str = "both",
    dry_run: bool = False,
    skip_existing: bool = True,
    templates_dir: Optional[Path] = None,
) -> list[GeneratedFile]:
    """Generate customisation files from templates.

    Parameters
    ----------
    context:
        Full placeholder context dict (from :func:`~bootstrap_iac.interview.build_context`).
    output_dir:
        Root directory where generated files are written.
    target:
        ``"copilot"``, ``"claude"``, or ``"both"``.
    dry_run:
        When *True*, do not write any files — just return the
        :class:`GeneratedFile` list.
    skip_existing:
        When *True* (default), do not overwrite files that already exist.
    templates_dir:
        Override the templates directory (default: auto-detected).

    Returns
    -------
    list[GeneratedFile]
        One entry per template, whether written, skipped, or dry-run.
    """
    tdir = templates_dir or get_templates_dir()
    specs = _build_output_specs(context, tdir)
    results: list[GeneratedFile] = []
    preparation_errors: list[str] = []

    for spec in specs:
        if target not in ("both",) and spec.target != target:
            continue

        tmpl_path = tdir / spec.template_rel
        out_path = output_dir / spec.output_rel
        if skip_existing and out_path.exists():
            results.append(
                GeneratedFile(
                    output_path=out_path,
                    template_path=tmpl_path,
                    content="",
                    skipped=True,
                    skip_reason="already exists",
                )
            )
            continue

        if not tmpl_path.exists():
            preparation_errors.append(
                f"missing template {tmpl_path} for {output_dir / spec.output_rel}"
            )
            continue

        try:
            raw = tmpl_path.read_text(encoding="utf-8")
        except OSError as exc:
            preparation_errors.append(f"unable to read template {tmpl_path}: {exc}")
            continue
        filled = resolve_placeholders(raw, context)
        unresolved = sorted(set(_PLACEHOLDER_RE.findall(filled)))
        if unresolved:
            preparation_errors.append(
                f"unresolved placeholder(s) for {out_path}: {', '.join(unresolved)}"
            )

        gf = GeneratedFile(
            output_path=out_path,
            template_path=tmpl_path,
            content=filled,
        )
        results.append(gf)

    if preparation_errors:
        raise GenerationError("Generation preflight failed:\n- " + "\n- ".join(preparation_errors))

    if dry_run:
        return results

    files_to_write = [result for result in results if not result.skipped]
    if not files_to_write:
        return results

    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging_dir = Path(
            tempfile.mkdtemp(prefix="bootstrap-iac-", dir=output_dir.parent)
        )
    except OSError as exc:
        raise GenerationError(f"Unable to create staging directory: {exc}") from exc

    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for result in files_to_write:
            staged_path = staging_dir / result.output_path.relative_to(output_dir)
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.write_text(result.content, encoding="utf-8")

        for result in files_to_write:
            output_path = result.output_path
            staged_path = staging_dir / output_path.relative_to(output_dir)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.exists():
                backup_path = staging_dir / ".backups" / output_path.relative_to(output_dir)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output_path, backup_path)
                backups[output_path] = backup_path
                staged_path.chmod(stat.S_IMODE(output_path.stat().st_mode))

            staged_path.replace(output_path)
            published.append(output_path)
    except (OSError, ValueError) as exc:
        rollback_errors: list[str] = []
        for output_path in reversed(published):
            try:
                output_path.unlink()
            except OSError as rollback_exc:
                rollback_errors.append(f"remove {output_path}: {rollback_exc}")
        for output_path, backup_path in backups.items():
            try:
                backup_path.replace(output_path)
            except OSError as rollback_exc:
                rollback_errors.append(f"restore {output_path}: {rollback_exc}")
        message = f"Unable to publish generated files: {exc}"
        if rollback_errors:
            message += "\nRollback errors:\n- " + "\n- ".join(rollback_errors)
        raise GenerationError(message) from exc
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    return results
