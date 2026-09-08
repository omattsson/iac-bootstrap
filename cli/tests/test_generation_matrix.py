"""Complete generation matrix and context-completeness tests (issue #58).

These tests exercise every supported combination of cloud provider,
orchestration tool, and generation target, verifying that:

- every combination renders without a :class:`GenerationError`;
- every combination produces the expected set of output files;
- rendered output contains no unresolved ``{{PLACEHOLDER}}`` tokens
  (i.e. :func:`build_context` supplies every key the templates need);
- cloud-specific overrides are used where they exist, and the base
  template is used as a fallback otherwise;
- a missing template or a missing context key fails with a message that
  names the offending template or placeholder.

The whole matrix runs offline — it only renders templates and never
contacts a cloud provider, so no credentials are required.
"""

from __future__ import annotations

import itertools

import pytest

from bootstrap_iac.generator import (
    GenerationError,
    _build_output_specs,
    generate_files,
    get_templates_dir,
)
from bootstrap_iac.interview import build_context
from bootstrap_iac.validator import find_unreplaced

# ---------------------------------------------------------------------------
# Matrix dimensions
# ---------------------------------------------------------------------------

CLOUDS = ["Azure", "AWS", "GCP"]
ORCHESTRATIONS = ["None", "Terragrunt", "Terramate", "Pulumi"]
TARGETS = ["copilot", "claude", "both"]
CICDS = ["GitHub Actions", "Azure DevOps", "GitLab CI", "Atlantis"]

# Orchestration tool -> lowercase slug used in generated output paths.
_ORCH_LOWER = {
    "None": "terraform",
    "Terragrunt": "terragrunt",
    "Terramate": "terramate",
    "Pulumi": "pulumi",
}

# Clouds that ship template overrides under ``<target>/<cloud>/``. Azure uses
# the base templates.
_CLOUD_OVERRIDE_DIRS = {"AWS": "aws", "GCP": "gcp"}


def _answers(cloud: str, orch: str, target: str, cicd: str = "GitHub Actions") -> dict:
    """Build a full set of interview answers for one matrix cell."""
    return {
        "COMPANY_NAME": "Acme Corp",
        "CLOUD_PROVIDER": cloud,
        "MODULE_PREFIX": "tf-module",
        "ORCHESTRATION_TOOL": orch,
        "ORCHESTRATION_DIR": "." if orch == "None" else "infrastructure-config",
        "CI_CD_PLATFORM": cicd,
        "AUTH_PATTERN": "",
        "TARGET": target,
        "ORG": "acme",
    }


# ---------------------------------------------------------------------------
# Expected output sets (an independent restatement of the generator's rules,
# so an accidental change to output paths is caught here).
# ---------------------------------------------------------------------------


def _expected_copilot(orch: str) -> set[str]:
    outputs = {
        ".github/copilot-instructions.md",
        ".github/agents/infra-architect.agent.md",
        ".github/agents/terraform-module-builder.agent.md",
        ".github/agents/terraform-test-writer.agent.md",
        ".github/skills/create-terraform-module/SKILL.md",
        ".github/skills/create-infra-pipeline/SKILL.md",
        ".github/instructions/terraform-modules.instructions.md",
        ".github/instructions/terraform-tests.instructions.md",
        ".github/instructions/pipeline-templates.instructions.md",
        ".github/instructions/iac-best-practices.instructions.md",
    }
    if orch != "None":
        low = _ORCH_LOWER[orch]
        outputs |= {
            f".github/agents/{low}-stack-manager.agent.md",
            f".github/skills/create-{low}-stack/SKILL.md",
            f".github/instructions/{low}-configs.instructions.md",
        }
    return outputs


def _expected_claude(orch: str) -> set[str]:
    outputs = {
        "CLAUDE.md",
        ".claude/commands/create-terraform-module.md",
        ".claude/commands/create-infra-pipeline.md",
    }
    if orch != "None":
        low = _ORCH_LOWER[orch]
        outputs |= {f".claude/commands/create-{low}-stack.md"}
    return outputs


def _expected_outputs(orch: str, target: str) -> set[str]:
    outputs: set[str] = set()
    if target in ("copilot", "both"):
        outputs |= _expected_copilot(orch)
    if target in ("claude", "both"):
        outputs |= _expected_claude(orch)
    return outputs


def _produced(results, root) -> set[str]:
    return {r.output_path.relative_to(root).as_posix() for r in results}


# ---------------------------------------------------------------------------
# The full matrix: cloud x orchestration x target
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cloud,orch,target",
    list(itertools.product(CLOUDS, ORCHESTRATIONS, TARGETS)),
)
def test_matrix_renders_expected_outputs_without_placeholders(
    tmp_path, cloud, orch, target
):
    ctx = build_context(_answers(cloud, orch, target))
    # dry_run still runs the full preflight (template existence + placeholder
    # resolution) and raises GenerationError on any gap.
    results = generate_files(ctx, tmp_path, target=target, dry_run=True)

    assert _produced(results, tmp_path) == _expected_outputs(orch, target)

    for result in results:
        leftover = find_unreplaced(result.content)
        assert leftover == [], (
            f"{cloud}/{orch}/{target}: unresolved in {result.output_path}: {leftover}"
        )


# ---------------------------------------------------------------------------
# Context completeness across CI/CD platforms (pipeline snippets)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cicd,orch",
    list(itertools.product(CICDS, ORCHESTRATIONS)),
)
def test_matrix_cicd_context_is_complete(tmp_path, cicd, orch):
    # Exercises the orchestration-aware pipeline generators
    # (_stack_pipeline / _drift_pipeline / _destroy_pipeline) for every CI/CD
    # platform and orchestration tool. These snippets do not depend on the
    # cloud, so a single cloud is enough here.
    ctx = build_context(_answers("Azure", orch, "both", cicd=cicd))
    results = generate_files(ctx, tmp_path, target="both", dry_run=True)
    for result in results:
        assert find_unreplaced(result.content) == [], (
            f"{cicd}/{orch}: unresolved in {result.output_path}"
        )


# ---------------------------------------------------------------------------
# Cloud overrides and fallback
# ---------------------------------------------------------------------------

# Output files whose source template has a per-cloud override for AWS and GCP.
_CLOUD_OVERRIDABLE = {
    ".github/copilot-instructions.md": "copilot/{cloud}/copilot-instructions.md.tmpl",
    ".github/agents/terraform-module-builder.agent.md": (
        "copilot/{cloud}/agents/terraform-module-builder.agent.md.tmpl"
    ),
    ".github/skills/create-terraform-module/SKILL.md": (
        "copilot/{cloud}/skills/create-terraform-module.skill.md.tmpl"
    ),
    ".github/instructions/terraform-modules.instructions.md": (
        "copilot/{cloud}/instructions/terraform-modules.instructions.md.tmpl"
    ),
    ".github/instructions/terraform-tests.instructions.md": (
        "copilot/{cloud}/instructions/terraform-tests.instructions.md.tmpl"
    ),
    "CLAUDE.md": "claude/{cloud}/CLAUDE.md.tmpl",
    ".claude/commands/create-terraform-module.md": (
        "claude/{cloud}/commands/create-terraform-module.md.tmpl"
    ),
}

# The same outputs, rendered from the base template.
_CLOUD_BASE = {
    ".github/copilot-instructions.md": "copilot/copilot-instructions.md.tmpl",
    ".github/agents/terraform-module-builder.agent.md": (
        "copilot/agents/terraform-module-builder.agent.md.tmpl"
    ),
    ".github/skills/create-terraform-module/SKILL.md": (
        "copilot/skills/create-terraform-module.skill.md.tmpl"
    ),
    ".github/instructions/terraform-modules.instructions.md": (
        "copilot/instructions/terraform-modules.instructions.md.tmpl"
    ),
    ".github/instructions/terraform-tests.instructions.md": (
        "copilot/instructions/terraform-tests.instructions.md.tmpl"
    ),
    "CLAUDE.md": "claude/CLAUDE.md.tmpl",
    ".claude/commands/create-terraform-module.md": (
        "claude/commands/create-terraform-module.md.tmpl"
    ),
}


@pytest.mark.parametrize(
    "cloud,backend,required,forbidden",
    [
        (
            "Azure",
            "azurerm",
            ["resource_group_name", "storage_account_name", "container_name", "key"],
            ["bucket", "prefix"],
        ),
        ("AWS", "s3", ["bucket", "key", "region"], ["resource_group_name", "prefix"]),
        ("GCP", "gcs", ["bucket", "prefix"], ["container_name", "resource_group_name"]),
    ],
)
def test_terramate_remote_state_example_is_valid_per_backend(
    cloud, backend, required, forbidden
):
    """The Terramate remote-state snippet is a valid config for each backend."""
    ctx = build_context(_answers(cloud, "Terramate", "both"))
    example = ctx["REMOTE_STATE_EXAMPLE"]
    assert f'backend = "{backend}"' in example
    for key in required:
        assert key in example, f"{cloud}: missing {key} in remote-state example"
    for key in forbidden:
        assert key not in example, f"{cloud}: unexpected {key} in remote-state example"


@pytest.mark.parametrize("cloud", CLOUDS)
def test_cloud_overrides_used_when_present_else_base(tmp_path, cloud):
    tdir = get_templates_dir()
    ctx = build_context(_answers(cloud, "None", "both"))
    results = generate_files(ctx, tmp_path, target="both", dry_run=True)
    by_output = {r.output_path.relative_to(tmp_path).as_posix(): r for r in results}

    for output_rel, override_pattern in _CLOUD_OVERRIDABLE.items():
        result = by_output[output_rel]
        tmpl_rel = result.template_path.relative_to(tdir).as_posix()
        if cloud in _CLOUD_OVERRIDE_DIRS:
            expected = override_pattern.format(cloud=_CLOUD_OVERRIDE_DIRS[cloud])
            # The override must actually exist on disk, and be the one chosen.
            assert (tdir / expected).exists(), f"missing override template {expected}"
            assert tmpl_rel == expected
        else:  # Azure — no override directory, falls back to the base template.
            assert tmpl_rel == _CLOUD_BASE[output_rel]


# ---------------------------------------------------------------------------
# Useful failures: missing template, missing context key
# ---------------------------------------------------------------------------


def test_missing_template_fails_with_named_message(tmp_path, monkeypatch):
    """A missing template names the template and its intended output."""
    import bootstrap_iac.generator as gen

    monkeypatch.setattr(
        gen,
        "_build_output_specs",
        lambda context, templates_dir: [
            gen.OutputSpec("does-not-exist.tmpl", "generated.md", "copilot")
        ],
    )
    with pytest.raises(GenerationError) as exc_info:
        generate_files({}, tmp_path, target="copilot", templates_dir=tmp_path)
    message = str(exc_info.value)
    assert "missing template" in message
    assert "does-not-exist.tmpl" in message


def test_missing_context_key_fails_with_named_placeholder(tmp_path):
    """Dropping a required context key surfaces the unresolved placeholder."""
    ctx = build_context(_answers("Azure", "None", "both"))
    ctx.pop("COMPANY_NAME", None)
    with pytest.raises(GenerationError) as exc_info:
        generate_files(ctx, tmp_path, target="both", dry_run=True)
    message = str(exc_info.value)
    assert "unresolved placeholder" in message
    assert "COMPANY_NAME" in message


# ---------------------------------------------------------------------------
# Guard: every bundled template is either generated or explicitly allowlisted
# ---------------------------------------------------------------------------

# Templates that ship in the package but are not produced by the CLI generator
# in any combination. They are used by the SKILL bootstrap procedure, not by
# `bootstrap-iac`, so they are not exercised by the matrix. Listing them here
# makes the omission explicit: a newly added template that is not wired into
# the generator will fail this test until it is either generated or added here
# with a reason.
_UNGENERATED_TEMPLATES = {
    # Extra Copilot instruction files applied by the SKILL procedure only.
    "copilot/instructions/checkov.instructions.md.tmpl",
    "copilot/instructions/opa.instructions.md.tmpl",
    "copilot/instructions/tflint.instructions.md.tmpl",
    "copilot/instructions/terratest.instructions.md.tmpl",
    # Multi-repo coordination helpers, applied by the SKILL procedure only.
    "copilot/agents/orchestration-coordinator.agent.md.tmpl",
    "claude/commands/coordinate-module-rollout.md.tmpl",
    # Standalone maturity report, produced by the SKILL procedure only.
    "maturity-report.md.tmpl",
}


def _all_referenced_templates() -> set[str]:
    """Every template path the generator can emit across the whole matrix."""
    tdir = get_templates_dir()
    referenced: set[str] = set()
    for cloud, orch in itertools.product(CLOUDS, ORCHESTRATIONS):
        ctx = build_context(_answers(cloud, orch, "both"))
        for spec in _build_output_specs(ctx, tdir):
            referenced.add(spec.template_rel)
    return referenced


def test_every_bundled_template_is_generated_or_allowlisted():
    """No template is silently unused; new orphans must be wired or listed."""
    tdir = get_templates_dir()
    on_disk = {p.relative_to(tdir).as_posix() for p in tdir.rglob("*.tmpl")}
    referenced = _all_referenced_templates()

    # Every referenced template must actually exist on disk.
    missing_on_disk = referenced - on_disk
    assert missing_on_disk == set(), f"referenced but absent: {sorted(missing_on_disk)}"

    # Every template on disk must be either generated or explicitly allowlisted.
    orphans = on_disk - referenced - _UNGENERATED_TEMPLATES
    assert orphans == set(), (
        "template(s) neither generated nor allowlisted: "
        f"{sorted(orphans)}. Wire them into _build_output_specs or add them to "
        "_UNGENERATED_TEMPLATES with a reason."
    )

    # Keep the allowlist honest: it must not name templates that no longer
    # exist or that are in fact generated.
    stale_allowlist = _UNGENERATED_TEMPLATES - (on_disk - referenced)
    assert stale_allowlist == set(), (
        f"stale entries in _UNGENERATED_TEMPLATES: {sorted(stale_allowlist)}"
    )
