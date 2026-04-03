"""Interactive interview to collect workspace parameters."""

from __future__ import annotations

import click

from bootstrap_iac.defaults import AUTH_DEFAULTS, CICD_DEFAULTS, CLOUD_DEFAULTS, ORCHESTRATION_DEFAULTS


def _prompt(message: str, default: str = "", choices: list[str] | None = None) -> str:
    """Wrapper around click.prompt that returns the default when non-interactive."""
    if choices:
        return click.prompt(
            message,
            default=default,
            type=click.Choice(choices),
            show_default=True,
        )
    return click.prompt(message, default=default, show_default=bool(default))


def run_interview(
    cloud_flag: str | None,
    non_interactive: bool,
    workspace_profile: dict,
) -> dict:
    """Run the interactive interview and return a dict of collected answers.

    When *non_interactive* is True every question uses its default value without
    prompting.  The *cloud_flag* value (from ``--cloud``) pre-fills the cloud
    provider answer.  *workspace_profile* (from discover.py) pre-fills defaults
    that can be inferred from the workspace.
    """

    # ------------------------------------------------------------------ #
    # Map CLI --cloud value to display name
    # ------------------------------------------------------------------ #
    cloud_display_map = {"azure": "Azure", "aws": "AWS", "gcp": "GCP"}
    prefilled_cloud = cloud_display_map.get((cloud_flag or "").lower(), "")

    # Determine sensible defaults from workspace discovery
    discovered_orchestration = "None"
    if workspace_profile.get("has_terragrunt"):
        discovered_orchestration = "Terragrunt"
    elif workspace_profile.get("has_terramate"):
        discovered_orchestration = "Terramate"

    discovered_cicd = "GitHub Actions"
    if workspace_profile.get("has_azure_devops") and not workspace_profile.get("has_github_actions"):
        discovered_cicd = "Azure DevOps"
    elif workspace_profile.get("has_gitlab_ci"):
        discovered_cicd = "GitLab CI"
    elif workspace_profile.get("has_atlantis"):
        discovered_cicd = "Atlantis"

    discovered_module_prefix = workspace_profile.get("module_prefix") or "tf-module"
    discovered_orch_dir = workspace_profile.get("orchestration_dir") or "infrastructure-config"
    discovered_pipeline_dir = workspace_profile.get("pipeline_dir") or ""

    if non_interactive:
        click.echo("Running in non-interactive mode — using defaults for all questions.")

    # ------------------------------------------------------------------ #
    # Q1  Company / org name
    # ------------------------------------------------------------------ #
    if non_interactive:
        company_name = "Acme Corp"
    else:
        company_name = _prompt("1. Company/organization name", default="Acme Corp")

    # ------------------------------------------------------------------ #
    # Q2  Cloud provider
    # ------------------------------------------------------------------ #
    cloud_choices = ["Azure", "AWS", "GCP"]
    if prefilled_cloud:
        cloud_provider = prefilled_cloud
        click.echo(f"2. Cloud provider: {cloud_provider}  (from --cloud flag)")
    elif non_interactive:
        cloud_provider = "Azure"
    else:
        cloud_provider = _prompt(
            "2. Cloud provider",
            default="Azure",
            choices=cloud_choices,
        )

    cloud_cfg = CLOUD_DEFAULTS[cloud_provider]

    # ------------------------------------------------------------------ #
    # Q3  Module prefix
    # ------------------------------------------------------------------ #
    if non_interactive:
        module_prefix = discovered_module_prefix
    else:
        module_prefix = _prompt(
            "3. Module prefix (directory naming, e.g. tf-module, terraform-aws)",
            default=discovered_module_prefix,
        )

    # ------------------------------------------------------------------ #
    # Q4  Module source pattern
    # ------------------------------------------------------------------ #
    org_default = company_name.lower().replace(" ", "")
    source_defaults = {
        "Azure": f"git::https://dev.azure.com/{org_default}/infra/_git/{module_prefix}-{{name}}?ref={{tag}}",
        "AWS": f"git::https://github.com/{org_default}/{module_prefix}-{{name}}?ref={{tag}}",
        "GCP": f"git::https://github.com/{org_default}/{module_prefix}-{{name}}?ref={{tag}}",
    }
    source_default = source_defaults.get(cloud_provider, source_defaults["AWS"])

    if non_interactive:
        module_source_pattern = source_default
    else:
        module_source_pattern = _prompt(
            "4. Module source pattern (Git URL template)",
            default=source_default,
        )

    # ------------------------------------------------------------------ #
    # Q5  Orchestration tool
    # ------------------------------------------------------------------ #
    orch_choices = ["Terragrunt", "Terramate", "None"]
    if non_interactive:
        orchestration_tool = discovered_orchestration
    else:
        orchestration_tool = _prompt(
            "5. Orchestration tool",
            default=discovered_orchestration,
            choices=orch_choices,
        )

    orch_cfg = ORCHESTRATION_DEFAULTS[orchestration_tool]

    # ------------------------------------------------------------------ #
    # Q6  Orchestration directory
    # ------------------------------------------------------------------ #
    orch_dir_default = discovered_orch_dir if discovered_orch_dir else "infrastructure-config"
    if orchestration_tool == "Terramate":
        orch_dir_default = workspace_profile.get("orchestration_dir") or "stacks"
    elif orchestration_tool == "None":
        orch_dir_default = "environments"

    if non_interactive:
        orchestration_dir = orch_dir_default
    else:
        if orchestration_tool != "None":
            orchestration_dir = _prompt(
                "6. Orchestration directory (where configs live)",
                default=orch_dir_default,
            )
        else:
            orchestration_dir = orch_dir_default
            click.echo(f"6. Orchestration directory: {orchestration_dir}  (no orchestration tool)")

    # ------------------------------------------------------------------ #
    # Q7  CI/CD platform
    # ------------------------------------------------------------------ #
    cicd_choices = ["GitHub Actions", "Azure DevOps", "GitLab CI", "Atlantis"]
    if non_interactive:
        cicd_platform = discovered_cicd
    else:
        cicd_platform = _prompt(
            "7. CI/CD platform",
            default=discovered_cicd,
            choices=cicd_choices,
        )

    cicd_cfg = CICD_DEFAULTS[cicd_platform]

    # ------------------------------------------------------------------ #
    # Q8  Auth pattern  (derived — not asked, but shown)
    # ------------------------------------------------------------------ #
    auth_defaults = AUTH_DEFAULTS.get(cloud_provider, {}).get(
        cicd_platform,
        AUTH_DEFAULTS.get(cloud_provider, {}).get("GitHub Actions", {}),
    )
    auth_pattern = auth_defaults.get("auth_pattern", "# Configure cloud authentication")
    auth_requirements = auth_defaults.get(
        "auth_requirements",
        "- Configure cloud credentials for your CI/CD platform",
    )

    # ------------------------------------------------------------------ #
    # Q9  Naming convention
    # ------------------------------------------------------------------ #
    naming_default = cloud_cfg["naming_pattern_default"]
    if non_interactive:
        naming_pattern = naming_default
    else:
        naming_pattern = _prompt(
            "9. Naming convention (e.g. {prefix}-{resource_abbreviation}-{suffix})",
            default=naming_default,
        )

    # ------------------------------------------------------------------ #
    # Q10  Tag/label standard
    # ------------------------------------------------------------------ #
    tag_merge = cloud_cfg["tag_merge_pattern"]
    tag_required_map = {
        "Azure": "environment, product, managed_by = \"Terraform\"",
        "AWS": "Environment, Product, ManagedBy = \"Terraform\"",
        "GCP": "environment, product, managed_by = \"terraform\"",
    }
    tag_required = tag_required_map.get(cloud_provider, "environment, product")

    # ------------------------------------------------------------------ #
    # Q11  Standard variables
    # ------------------------------------------------------------------ #
    std_vars_default = cloud_cfg["standard_variables_default"]
    if non_interactive:
        standard_variables = std_vars_default
    else:
        click.echo(
            f"\n11. Standard variables (cross-module variables). Default:\n{std_vars_default}\n"
        )
        use_default = click.confirm("    Use these defaults?", default=True)
        if use_default:
            standard_variables = std_vars_default
        else:
            standard_variables = click.edit(std_vars_default) or std_vars_default

    # ------------------------------------------------------------------ #
    # Q12  Version tag location
    # ------------------------------------------------------------------ #
    version_tag_default = orch_cfg.get("version_tag_location_default", "module version file")
    if non_interactive:
        version_tag_location = version_tag_default
    else:
        version_tag_location = _prompt(
            "12. Version tag location (where module version pins are stored)",
            default=version_tag_default,
        )

    # ------------------------------------------------------------------ #
    # Q13  Target tools
    # ------------------------------------------------------------------ #
    tool_choices = ["both", "copilot", "claude"]
    if non_interactive:
        target_tools = "both"
    else:
        target_tools = _prompt(
            "13. Generate output for",
            default="both",
            choices=tool_choices,
        )

    # ------------------------------------------------------------------ #
    # Pipeline dir (derived from CI/CD)
    # ------------------------------------------------------------------ #
    pipeline_dir = discovered_pipeline_dir or cicd_cfg.get("pipeline_dir", ".github/workflows")

    # ------------------------------------------------------------------ #
    # Org (derived from company name)
    # ------------------------------------------------------------------ #
    org = company_name.lower().replace(" ", "")

    return {
        "company_name": company_name,
        "cloud_provider": cloud_provider,
        "module_prefix": module_prefix,
        "module_source_pattern": module_source_pattern,
        "orchestration_tool": orchestration_tool,
        "orchestration_dir": orchestration_dir,
        "cicd_platform": cicd_platform,
        "auth_pattern": auth_pattern,
        "auth_requirements": auth_requirements,
        "naming_pattern": naming_pattern,
        "tag_merge": tag_merge,
        "tag_required": tag_required,
        "standard_variables": standard_variables,
        "version_tag_location": version_tag_location,
        "target_tools": target_tools,
        "pipeline_dir": pipeline_dir,
        "org": org,
    }
