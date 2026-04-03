"""Template rendering and output file generation."""

from __future__ import annotations

import re
from pathlib import Path

from bootstrap_iac.defaults import CICD_DEFAULTS, CLOUD_DEFAULTS, ORCHESTRATION_DEFAULTS


# ---------------------------------------------------------------------------
# Template discovery
# ---------------------------------------------------------------------------

def find_templates_dir() -> Path:
    """Locate the templates/references directory.

    Checks two locations in order:
    1. ``<package_root>/../../references/``  — works when running from a repo clone
       or an editable (``pip install -e .``) install.
    2. ``<package_root>/templates/``          — works when templates are bundled
       inside the installed package (``pip install``).
    """
    pkg_root = Path(__file__).resolve().parent

    repo_refs = pkg_root.parent / "references"
    if repo_refs.exists():
        return repo_refs

    bundled = pkg_root / "templates"
    if bundled.exists():
        return bundled

    raise FileNotFoundError(
        "Cannot find templates directory. "
        "Expected 'references/' in the repository root "
        "or 'bootstrap_iac/templates/' for installed packages. "
        "Re-clone the repo or reinstall the package."
    )


# ---------------------------------------------------------------------------
# Placeholder building
# ---------------------------------------------------------------------------

def _build_test_standard_variables(standard_variables: str) -> str:
    """Convert a bullet-list of standard variables into a HCL variables {} block."""
    lines = []
    for line in standard_variables.splitlines():
        line = line.strip().lstrip("- ").strip()
        if not line:
            continue
        # Extract variable name (before " — " or " - " description)
        var_name = re.split(r"\s+[—–-]\s+", line)[0].strip().strip("`")
        if var_name:
            lines.append(f'  {var_name} = "mock-{var_name}"')
    return "variables {\n" + "\n".join(lines) + "\n}"


def _build_naming_locals(naming_pattern: str, cloud_provider: str) -> str:
    """Generate a HCL locals block for naming."""
    cloud_cfg = CLOUD_DEFAULTS[cloud_provider]
    provider_name = cloud_cfg["provider_name"]

    if provider_name == "azurerm":
        return (
            "locals {\n"
            "  suffix = replace(var.suffix, \"/[^0-9A-Za-z]+/\", \"-\")\n"
            '  name   = substr("${var.prefix}-${local.suffix}", 0, 24)\n'
            "  tags   = merge(var.env_default_tags, var.tags)\n"
            "}"
        )
    elif provider_name == "aws":
        return (
            "locals {\n"
            "  suffix = replace(var.suffix, \"/[^0-9A-Za-z]+/\", \"-\")\n"
            '  name   = "${var.prefix}-${local.suffix}"\n'
            "  tags   = merge(var.default_tags, var.tags)\n"
            "}"
        )
    else:
        return (
            "locals {\n"
            "  suffix = replace(var.suffix, \"/[^0-9A-Za-z]+/\", \"-\")\n"
            '  name   = "${var.prefix}-${local.suffix}"\n'
            "  labels = merge(var.labels, var.extra_labels)\n"
            "}"
        )


def _build_naming_pattern_hcl(naming_pattern: str, cloud_provider: str) -> str:
    """Generate a HCL naming expression for locals.tf."""
    cloud_cfg = CLOUD_DEFAULTS[cloud_provider]
    provider_name = cloud_cfg["provider_name"]

    if provider_name == "azurerm":
        return (
            'locals {\n'
            '  name = substr(\n'
            '    "${var.prefix}-${replace(var.suffix, "/[^0-9A-Za-z]+/", "-")}",\n'
            '    0,\n'
            '    24\n'
            '  )\n'
            '}'
        )
    elif provider_name == "aws":
        return (
            'locals {\n'
            '  name = "${var.prefix}-${replace(var.suffix, "/[^0-9A-Za-z]+/", "-")}"\n'
            '}'
        )
    else:
        return (
            'locals {\n'
            '  name = "${var.prefix}-${replace(var.suffix, "/[^0-9A-Za-z]+/", "-")}"\n'
            '}'
        )


def _build_provider_block(cloud_provider: str) -> str:
    """Generate a provider versions.tf block."""
    cloud_cfg = CLOUD_DEFAULTS[cloud_provider]
    provider_name = cloud_cfg["provider_name"]
    version = cloud_cfg["provider_version_constraints"]

    return (
        "terraform {\n"
        "  required_providers {\n"
        f'    {provider_name} = {{\n'
        f'      source  = "hashicorp/{provider_name}"\n'
        f'      version = "{version}"\n'
        "    }\n"
        "  }\n"
        '  required_version = ">= 1.3.0"\n'
        "}"
    )


def _build_provider_version_constraints(cloud_provider: str) -> str:
    """Generate a provider version constraints string for display."""
    cloud_cfg = CLOUD_DEFAULTS[cloud_provider]
    provider_name = cloud_cfg["provider_name"]
    version = cloud_cfg["provider_version_constraints"]
    return (
        "required_providers {\n"
        f'  {provider_name} = {{\n'
        f'    source  = "hashicorp/{provider_name}"\n'
        f'    version = "{version}"\n'
        "  }\n"
        "}"
    )


def _build_tag_strategy(cloud_provider: str, tag_merge: str, tag_required: str) -> str:
    """Generate a tag strategy description."""
    cloud_cfg = CLOUD_DEFAULTS[cloud_provider]
    provider_name = cloud_cfg["provider_name"]

    if provider_name == "google":
        label_key = "labels"
        tag_word = "labels"
    else:
        label_key = "tags"
        tag_word = "tags"

    return (
        f"```hcl\n"
        f"local.{label_key} = {tag_merge}\n"
        f"```\n"
        f"Always merge environment defaults with resource-specific {tag_word}. "
        f"Resource-specific wins on key conflicts.\n"
        f"Required {tag_word}: {tag_required}."
    )


def _build_pipeline_snippets(cloud_provider: str, cicd_platform: str, orchestration_tool: str,
                              orchestration_dir: str, auth_pattern: str) -> dict:
    """Generate pipeline YAML snippet placeholders."""
    orch_cfg = ORCHESTRATION_DEFAULTS[orchestration_tool]
    plan_cmd = orch_cfg["plan_command"]
    extra_flags = orch_cfg.get("extra_run_flags", "")

    if cicd_platform == "GitHub Actions":
        single_pipeline = (
            "```yaml\n"
            "name: Plan\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  plan:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - name: Authenticate\n"
            "        # See auth pattern above\n"
            f"      - name: {orchestration_tool} Plan\n"
            f"        run: {plan_cmd} {extra_flags}\n"
            f"        working-directory: {orchestration_dir}\n"
            "```"
        )
        stack_pipeline = (
            "```yaml\n"
            "name: Plan All\n"
            "on:\n"
            "  push:\n"
            "    branches: [main]\n"
            "jobs:\n"
            "  plan-all:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            f"      - run: {orch_cfg['plan_all_command']} {extra_flags}\n"
            f"        working-directory: {orchestration_dir}\n"
            "```"
        )
        drift_pipeline = (
            "```yaml\n"
            "name: Drift Detection\n"
            "on:\n"
            "  schedule:\n"
            "    - cron: '0 6 * * *'\n"
            "jobs:\n"
            "  drift:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            f"      - run: {orch_cfg['plan_all_command']} {extra_flags}\n"
            f"        working-directory: {orchestration_dir}\n"
            "```"
        )
    elif cicd_platform == "Azure DevOps":
        single_pipeline = (
            "```yaml\n"
            "stages:\n"
            "  - stage: Plan\n"
            "    jobs:\n"
            "      - job: plan\n"
            "        steps:\n"
            f"          - script: {plan_cmd} {extra_flags}\n"
            f"            workingDirectory: $(System.DefaultWorkingDirectory)/{orchestration_dir}\n"
            "```"
        )
        stack_pipeline = (
            "```yaml\n"
            "stages:\n"
            "  - stage: PlanAll\n"
            "    jobs:\n"
            "      - job: planAll\n"
            "        steps:\n"
            f"          - script: {orch_cfg['plan_all_command']} {extra_flags}\n"
            f"            workingDirectory: $(System.DefaultWorkingDirectory)/{orchestration_dir}\n"
            "```"
        )
        drift_pipeline = (
            "```yaml\n"
            "schedules:\n"
            "  - cron: '0 6 * * *'\n"
            "    displayName: Drift Detection\n"
            "    branches:\n"
            "      include: [main]\n"
            "stages:\n"
            "  - stage: DriftCheck\n"
            "    jobs:\n"
            "      - job: drift\n"
            "        steps:\n"
            f"          - script: {orch_cfg['plan_all_command']} {extra_flags}\n"
            "```"
        )
    else:
        single_pipeline = f"Run: `{plan_cmd} {extra_flags}` in `{orchestration_dir}/`"
        stack_pipeline = f"Run: `{orch_cfg['plan_all_command']} {extra_flags}` in `{orchestration_dir}/`"
        drift_pipeline = f"Schedule: `{orch_cfg['plan_all_command']} {extra_flags}` (daily)"

    return {
        "single_component_pipeline": single_pipeline,
        "stack_pipeline": stack_pipeline,
        "drift_pipeline": drift_pipeline,
    }


def build_placeholders(answers: dict) -> dict[str, str]:
    """Build the full placeholder mapping from interview answers."""
    company = answers["company_name"]
    cloud = answers["cloud_provider"]
    module_prefix = answers["module_prefix"]
    orchestration_tool = answers["orchestration_tool"]
    orchestration_dir = answers["orchestration_dir"]
    cicd_platform = answers["cicd_platform"]
    naming_pattern = answers["naming_pattern"]
    standard_variables = answers["standard_variables"]
    tag_merge = answers["tag_merge"]
    tag_required = answers["tag_required"]
    version_tag_location = answers["version_tag_location"]
    pipeline_dir = answers["pipeline_dir"]
    org = answers["org"]
    auth_pattern = answers["auth_pattern"]
    auth_requirements = answers["auth_requirements"]
    module_source_pattern = answers["module_source_pattern"]

    cloud_cfg = CLOUD_DEFAULTS[cloud]
    orch_cfg = ORCHESTRATION_DEFAULTS[orchestration_tool]
    cicd_cfg = CICD_DEFAULTS[cicd_platform]

    pipeline_snippets = _build_pipeline_snippets(
        cloud, cicd_platform, orchestration_tool, orchestration_dir, auth_pattern
    )

    # Environment hierarchy with a human-readable label
    env_hierarchy = orch_cfg["environment_hierarchy"].replace(
        "config/", f"{orchestration_dir}/"
    )

    return {
        # Core identifiers
        "COMPANY_NAME": company,
        "CLOUD_PROVIDER": cloud,
        "MODULE_PREFIX": module_prefix,
        "ORCHESTRATION_TOOL": orchestration_tool if orchestration_tool != "None" else "plain Terraform",
        "ORCHESTRATION_TOOL_LOWER": orch_cfg["lower"],
        "ORCHESTRATION_DIR": orchestration_dir,
        "CI_CD_PLATFORM": cicd_platform,
        "PIPELINE_DIR": pipeline_dir,
        "ORG": org,
        "PROJECT": f"{org}-infra",
        # Provider
        "PROVIDER_NAME": cloud_cfg["provider_name"],
        "PROVIDER_RESOURCE": cloud_cfg["provider_resource"],
        "PROVIDER_RESOURCE_EXAMPLE": cloud_cfg["provider_resource_example"],
        "LOCATION_ATTRIBUTE": cloud_cfg["location_attribute"],
        "RESOURCE_GROUP_ATTRIBUTE": cloud_cfg["resource_group_attribute"],
        "PROVIDER_BLOCK": _build_provider_block(cloud),
        "PROVIDER_VERSION_CONSTRAINTS": _build_provider_version_constraints(cloud),
        # Module conventions
        "MODULE_SOURCE_PATTERN": (
            f"```\n{module_source_pattern}\n```"
        ),
        "MODULE_SOURCE_CONVENTION": module_source_pattern,
        "RESOURCE_IDENTIFIER": "default",
        "COMMON_VARS_FILE": "common.variables.tf",
        "VERSION_TAG_LOCATION": version_tag_location,
        # Naming
        "NAMING_PATTERN": naming_pattern,
        "NAMING_PATTERN_HCL": _build_naming_pattern_hcl(naming_pattern, cloud),
        "NAMING_LOCALS": _build_naming_locals(naming_pattern, cloud),
        "EXPECTED_NAME_PATTERN": f"test-auto-{cloud_cfg['provider_name'][:2]}-mysuffix",
        # Tagging
        "TAG_MERGE_PATTERN": tag_merge,
        "TAG_MERGE_LOCAL": f"tags = {tag_merge}",
        "TAG_STRATEGY": _build_tag_strategy(cloud, tag_merge, tag_required),
        # Variables
        "STANDARD_VARIABLES": standard_variables,
        "TEST_STANDARD_VARIABLES": _build_test_standard_variables(standard_variables),
        "DATA_SOURCE_OVERRIDE": cloud_cfg["data_source_override"],
        "OPTIONAL_FEATURES": cloud_cfg["optional_features"],
        "VARIABLE_GOTCHAS": cloud_cfg["variable_gotchas"],
        "PRIVATE_ENDPOINT_PATTERN": cloud_cfg["private_endpoint_pattern"],
        # Orchestration
        "VALIDATE_COMMAND": orch_cfg["validate_command"],
        "PLAN_COMMAND": orch_cfg["plan_command"],
        "PLAN_ALL_COMMAND": orch_cfg["plan_all_command"],
        "PLAN_SINGLE_COMMAND": orch_cfg["plan_single_command"],
        "GRAPH_COMMAND": orch_cfg["graph_command"],
        "EXTRA_RUN_FLAGS": orch_cfg["extra_run_flags"],
        "ENVCOMMON_PATTERN": orch_cfg["envcommon_pattern"],
        "ENVIRONMENT_HIERARCHY": orch_cfg["environment_hierarchy"],
        "HIERARCHY_DIAGRAM": orch_cfg["hierarchy_diagram"],
        "HIERARCHY_FILES_DESCRIPTION": orch_cfg["hierarchy_files_description"],
        "INPUT_FLOW_DIAGRAM": orch_cfg["input_flow_diagram"],
        "COMPONENT_CONFIG_PATTERN": orch_cfg["component_config_pattern"],
        "COMPONENT_CONFIG_TEMPLATE": orch_cfg["component_config_pattern"],
        "ENVCOMMON_TEMPLATE": orch_cfg["envcommon_template"],
        "STACK_CONFIG_TEMPLATE": orch_cfg["envcommon_template"],
        "SITE_CONFIG_TEMPLATE": orch_cfg["envcommon_template"],
        "MOCK_OUTPUTS_EXAMPLE": orch_cfg["mock_outputs_example"],
        "DEPENDENCY_CONVENTIONS": orch_cfg["dependency_conventions"],
        # CI/CD
        "PIPELINE_APPLY_TO": cicd_cfg["pipeline_apply_to"],
        "TEMPLATE_REFERENCE_PATTERN": cicd_cfg["template_reference_pattern"],
        "AUTH_PATTERN": auth_pattern,
        "AUTH_REQUIREMENTS": auth_requirements,
        "STANDARD_PARAMETERS": cicd_cfg["standard_parameters"],
        "STANDARD_PARAMETERS_LIST": cicd_cfg["standard_parameters_list"],
        "PIPELINE_CONVENTIONS": cicd_cfg["pipeline_conventions"],
        "PIPELINE_CONVENTIONS_LIST": cicd_cfg["pipeline_conventions_list"],
        "SINGLE_COMPONENT_PIPELINE": pipeline_snippets["single_component_pipeline"],
        "STACK_PIPELINE": pipeline_snippets["stack_pipeline"],
        "DRIFT_PIPELINE": pipeline_snippets["drift_pipeline"],
        "PIPELINE_TEMPLATES_REPO": f"{pipeline_dir}",
        # Misc
        "VERSION_TAG_EXAMPLE": f"{module_prefix}-keyvault → v1.2.3",
    }


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def render_template(template_path: Path, placeholders: dict[str, str]) -> str:
    """Read a .tmpl file and substitute all ``{{PLACEHOLDER}}`` tokens."""
    content = template_path.read_text(encoding="utf-8")
    for key, value in placeholders.items():
        content = content.replace("{{" + key + "}}", value or f"# TODO: set {key}")
    return content


# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------

#: Maps (template_path_relative_to_references, output_path) for Copilot output.
#: Output paths use ``{orchestration_tool_lower}`` as a format key for the
#: orchestration-stack-manager agent name.
COPILOT_FILE_MAP = [
    (
        "copilot/copilot-instructions.md.tmpl",
        ".github/copilot-instructions.md",
    ),
    (
        "copilot/agents/infra-architect.agent.md.tmpl",
        ".github/agents/infra-architect.agent.md",
    ),
    (
        "copilot/agents/terraform-module-builder.agent.md.tmpl",
        ".github/agents/terraform-module-builder.agent.md",
    ),
    (
        "copilot/agents/terraform-test-writer.agent.md.tmpl",
        ".github/agents/terraform-test-writer.agent.md",
    ),
    (
        "copilot/skills/create-terraform-module.skill.md.tmpl",
        ".github/skills/create-terraform-module/SKILL.md",
    ),
    (
        "copilot/skills/create-infra-pipeline.skill.md.tmpl",
        ".github/skills/create-infra-pipeline/SKILL.md",
    ),
    (
        "copilot/instructions/terraform-modules.instructions.md.tmpl",
        ".github/instructions/terraform-modules.instructions.md",
    ),
    (
        "copilot/instructions/terraform-tests.instructions.md.tmpl",
        ".github/instructions/terraform-tests.instructions.md",
    ),
    (
        "copilot/instructions/pipeline-templates.instructions.md.tmpl",
        ".github/instructions/pipeline-templates.instructions.md",
    ),
    (
        "copilot/instructions/iac-best-practices.instructions.md.tmpl",
        ".github/instructions/iac-best-practices.instructions.md",
    ),
]

#: Extra files generated only when an orchestration tool is active.
ORCHESTRATION_COPILOT_FILE_MAP = [
    (
        "copilot/agents/orchestration-stack-manager.agent.md.tmpl",
        ".github/agents/{orchestration_tool_lower}-stack-manager.agent.md",
    ),
    (
        "copilot/skills/create-orchestration-stack.skill.md.tmpl",
        ".github/skills/create-{orchestration_tool_lower}-stack/SKILL.md",
    ),
    (
        "copilot/instructions/orchestration-configs.instructions.md.tmpl",
        ".github/instructions/{orchestration_tool_lower}-configs.instructions.md",
    ),
]

CLAUDE_FILE_MAP = [
    (
        "claude/CLAUDE.md.tmpl",
        "CLAUDE.md",
    ),
    (
        "claude/commands/create-terraform-module.md.tmpl",
        ".claude/commands/create-terraform-module.md",
    ),
    (
        "claude/commands/create-infra-pipeline.md.tmpl",
        ".claude/commands/create-infra-pipeline.md",
    ),
]

ORCHESTRATION_CLAUDE_FILE_MAP = [
    (
        "claude/commands/create-orchestration-stack.md.tmpl",
        ".claude/commands/create-{orchestration_tool_lower}-stack.md",
    ),
]


def _resolve_output_path(template_output: str, placeholders: dict[str, str]) -> str:
    """Substitute ``{orchestration_tool_lower}`` placeholders in output path."""
    return template_output.format(
        orchestration_tool_lower=placeholders.get("ORCHESTRATION_TOOL_LOWER", "orchestration")
    )


def generate_files(
    answers: dict,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Generate all output files from templates.

    Returns a tuple of (written, skipped) path lists.
    """
    templates_dir = find_templates_dir()
    placeholders = build_placeholders(answers)

    tools = answers.get("target_tools", "both")
    use_copilot = tools in ("copilot", "both")
    use_claude = tools in ("claude", "both")
    use_orchestration = answers.get("orchestration_tool", "None") != "None"

    file_map: list[tuple[str, str]] = []

    if use_copilot:
        file_map.extend(COPILOT_FILE_MAP)
        if use_orchestration:
            file_map.extend(ORCHESTRATION_COPILOT_FILE_MAP)

    if use_claude:
        file_map.extend(CLAUDE_FILE_MAP)
        if use_orchestration:
            file_map.extend(ORCHESTRATION_CLAUDE_FILE_MAP)

    written: list[Path] = []
    skipped: list[Path] = []

    for template_rel, output_rel in file_map:
        template_path = templates_dir / template_rel
        if not template_path.exists():
            click_echo_warning(f"Template not found, skipping: {template_path}")
            continue

        output_rel_resolved = _resolve_output_path(output_rel, placeholders)
        output_path = output_dir / output_rel_resolved

        if output_path.exists() and not overwrite:
            skipped.append(output_path)
            continue

        rendered = render_template(template_path, placeholders)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        written.append(output_path)

    return written, skipped


def click_echo_warning(message: str) -> None:
    """Print a warning message to stderr."""
    import click
    click.echo(f"WARNING: {message}", err=True)
