"""Template engine and file generation.

Reads ``*.tmpl`` files from the bundled ``templates/`` directory, replaces all
``{{PLACEHOLDER}}`` tokens with values from *context*, and writes the results
to an output directory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

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


_CLOUD_SUBDIRS: dict[str, str] = {
    "AWS": "aws",
    "GCP": "gcp",
}


def _cloud_template(base_rel: str, cloud: str, templates_dir: Path | None) -> str:
    """Return the cloud-specific template path if it exists, else the base path.

    For AWS/GCP the convention is to check for a variant under the cloud
    subdirectory (e.g. ``copilot/aws/copilot-instructions.md.tmpl``).
    Azure (the default) always uses the base templates.
    """
    subdir = _CLOUD_SUBDIRS.get(cloud)
    if not subdir:
        return base_rel

    # Build candidate: insert cloud subdir after the tool prefix
    # e.g. "copilot/agents/foo.tmpl" → "copilot/aws/agents/foo.tmpl"
    parts = base_rel.split("/", 1)
    if len(parts) != 2:
        return base_rel
    candidate = f"{parts[0]}/{subdir}/{parts[1]}"

    # Only return the candidate when a concrete templates_dir is available and
    # the file actually exists there.  This avoids referencing cloud paths when
    # the bundled templates do not ship the variant.
    if templates_dir is not None and (templates_dir / candidate).exists():
        return candidate

    return base_rel


def _build_output_specs(context: dict, templates_dir: Path | None = None) -> list[OutputSpec]:
    """Return the list of files to generate based on *context*."""
    orch_lower = context.get("ORCHESTRATION_TOOL_LOWER", "terraform")
    has_orchestration = context.get("ORCHESTRATION_TOOL", "None") != "None"
    cloud = context.get("CLOUD_PROVIDER", "Azure")

    def _ct(base: str) -> str:
        return _cloud_template(base, cloud, templates_dir)

    specs: list[OutputSpec] = []

    # ---- Copilot outputs ----
    specs += [
        OutputSpec(
            _ct("copilot/copilot-instructions.md.tmpl"),
            ".github/copilot-instructions.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/agents/infra-architect.agent.md.tmpl"),
            ".github/agents/infra-architect.agent.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/agents/terraform-module-builder.agent.md.tmpl"),
            ".github/agents/terraform-module-builder.agent.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/agents/terraform-test-writer.agent.md.tmpl"),
            ".github/agents/terraform-test-writer.agent.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/skills/create-terraform-module.skill.md.tmpl"),
            ".github/skills/create-terraform-module/SKILL.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/skills/create-infra-pipeline.skill.md.tmpl"),
            ".github/skills/create-infra-pipeline/SKILL.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/instructions/terraform-modules.instructions.md.tmpl"),
            ".github/instructions/terraform-modules.instructions.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/instructions/terraform-tests.instructions.md.tmpl"),
            ".github/instructions/terraform-tests.instructions.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/instructions/pipeline-templates.instructions.md.tmpl"),
            ".github/instructions/pipeline-templates.instructions.md",
            "copilot",
        ),
        OutputSpec(
            _ct("copilot/instructions/iac-best-practices.instructions.md.tmpl"),
            ".github/instructions/iac-best-practices.instructions.md",
            "copilot",
        ),
    ]

    if has_orchestration:
        specs += [
            OutputSpec(
                _ct("copilot/agents/orchestration-stack-manager.agent.md.tmpl"),
                f".github/agents/{orch_lower}-stack-manager.agent.md",
                "copilot",
            ),
            OutputSpec(
                _ct("copilot/skills/create-orchestration-stack.skill.md.tmpl"),
                f".github/skills/create-{orch_lower}-stack/SKILL.md",
                "copilot",
            ),
            OutputSpec(
                _ct("copilot/instructions/orchestration-configs.instructions.md.tmpl"),
                f".github/instructions/{orch_lower}-configs.instructions.md",
                "copilot",
            ),
        ]

    # ---- Claude Code outputs ----
    specs += [
        OutputSpec(
            _ct("claude/CLAUDE.md.tmpl"),
            "CLAUDE.md",
            "claude",
        ),
        OutputSpec(
            _ct("claude/commands/create-terraform-module.md.tmpl"),
            ".claude/commands/create-terraform-module.md",
            "claude",
        ),
        OutputSpec(
            _ct("claude/commands/create-infra-pipeline.md.tmpl"),
            ".claude/commands/create-infra-pipeline.md",
            "claude",
        ),
    ]

    if has_orchestration:
        specs.append(
            OutputSpec(
                _ct("claude/commands/create-orchestration-stack.md.tmpl"),
                ".claude/commands/create-orchestration-stack.md",
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
    specs = _build_output_specs(context, templates_dir=tdir)
    results: list[GeneratedFile] = []

    for spec in specs:
        if target not in ("both",) and spec.target != target:
            continue

        tmpl_path = tdir / spec.template_rel
        if not tmpl_path.exists():
            continue

        raw = tmpl_path.read_text(encoding="utf-8")
        filled = resolve_placeholders(raw, context)
        out_path = output_dir / spec.output_rel

        skipped = False
        skip_reason = ""
        if skip_existing and out_path.exists():
            skipped = True
            skip_reason = "already exists"

        gf = GeneratedFile(
            output_path=out_path,
            template_path=tmpl_path,
            content=filled,
            skipped=skipped,
            skip_reason=skip_reason,
        )
        results.append(gf)

        if not dry_run and not skipped:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(filled, encoding="utf-8")

    return results
