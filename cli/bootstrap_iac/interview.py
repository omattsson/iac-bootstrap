"""Interactive interview to collect workspace configuration values.

This module drives the question-and-answer session that converts raw user
answers into a complete ``context`` dict that the generator can use to fill
all ``{{PLACEHOLDER}}`` tokens in the templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click

from bootstrap_iac.discovery import DiscoveryResult


# ---------------------------------------------------------------------------
# Cloud-provider-specific defaults
# ---------------------------------------------------------------------------

_CLOUD_PROVIDER_DEFAULTS: dict[str, dict] = {
    "Azure": {
        "provider_name": "azurerm",
        "provider_version_constraints": ">=4.0.0,<5.0.0",
        "provider_resource_example": "azurerm_resource_group.default",
        "location_attribute": "location = var.location",
        "resource_group_attribute": "resource_group_name = var.resource_group_name",
        "state_backend": "Azure Blob Storage",
        "auth_pattern": "Managed Identity / OIDC",
        "standard_variables": (
            "- `prefix` — Resource name prefix\n"
            "- `location` — Azure region (e.g. westeurope)\n"
            "- `resource_group_name` — Target resource group\n"
            "- `tags` — Resource-specific tags (map(string))\n"
            "- `env_default_tags` — Environment-wide default tags from orchestration"
        ),
        "naming_pattern": "{prefix}-{resource_abbreviation}-{suffix}",
        "tag_strategy": (
            "local.tags = merge(var.env_default_tags, var.tags)\n"
            "Required tags: environment, product, managed_by = \"Terraform\""
        ),
        "private_endpoint_pattern": (
            "Every resource that supports private endpoints must expose an "
            "`enable_private_endpoint` variable (bool, default false). "
            "When true, create an azurerm_private_endpoint named "
            "\"${local.name}-pe\" within var.private_endpoint_subnet_id."
        ),
    },
    "AWS": {
        "provider_name": "aws",
        "provider_version_constraints": ">=5.0.0,<6.0.0",
        "provider_resource_example": "aws_s3_bucket.default",
        "location_attribute": "region = var.region",
        "resource_group_attribute": "",
        "state_backend": "S3",
        "auth_pattern": "IAM Roles via OIDC",
        "standard_variables": (
            "- `prefix` — Resource name prefix\n"
            "- `region` — AWS region (e.g. us-east-1)\n"
            "- `tags` — Resource-specific tags (map(string))\n"
            "- `default_tags` — Account-wide default tags from orchestration"
        ),
        "naming_pattern": "{prefix}-{resource_type}-{suffix}",
        "tag_strategy": (
            "local.tags = merge(var.default_tags, var.tags)\n"
            "Required tags: Environment, Product, ManagedBy = \"Terraform\""
        ),
        "private_endpoint_pattern": (
            "Use VPC endpoints for private connectivity. "
            "Expose `enable_vpc_endpoint` variable (bool, default false)."
        ),
    },
    "GCP": {
        "provider_name": "google",
        "provider_version_constraints": ">=5.0.0,<6.0.0",
        "provider_resource_example": "google_storage_bucket.default",
        "location_attribute": "location = var.location",
        "resource_group_attribute": "project = var.project",
        "state_backend": "GCS",
        "auth_pattern": "Workload Identity Federation",
        "standard_variables": (
            "- `prefix` — Resource name prefix\n"
            "- `location` — GCP region or zone\n"
            "- `project` — GCP project ID\n"
            "- `labels` — Resource labels (map(string))\n"
            "- `default_labels` — Project-wide default labels from orchestration"
        ),
        "naming_pattern": "{prefix}-{resource_type}-{suffix}",
        "tag_strategy": (
            "local.labels = merge(var.default_labels, var.labels)\n"
            "Required labels: environment, product, managed_by = \"terraform\""
        ),
        "private_endpoint_pattern": (
            "Use Private Service Connect for private connectivity. "
            "Expose `enable_private_service_connect` variable (bool, default false)."
        ),
    },
}

# ---------------------------------------------------------------------------
# Orchestration-tool-specific defaults
# ---------------------------------------------------------------------------

_ORCHESTRATION_DEFAULTS: dict[str, dict] = {
    "Terragrunt": {
        "tool_lower": "terragrunt",
        "validate_command": "terragrunt validate",
        "plan_command": "terragrunt plan",
        "plan_all_command": "terragrunt run-all plan",
        "plan_single_command": "terragrunt plan",
        "graph_command": "terragrunt graph-dependencies",
        "extra_run_flags": "--terragrunt-non-interactive",
        "envcommon_pattern": "_envcommon/*.hcl",
        "hierarchy_diagram": (
            "config/\n"
            "├── subscription.hcl          # account/subscription ID, module versions\n"
            "└── {environment}/\n"
            "    ├── site.hcl              # region, location\n"
            "    └── {stack}/\n"
            "        ├── stack.hcl         # stack name, prefix\n"
            "        ├── _envcommon/       # shared module configs\n"
            "        │   └── {module}.hcl\n"
            "        └── {component}/\n"
            "            └── terragrunt.hcl"
        ),
        "hierarchy_files_description": (
            "- `subscription.hcl` — subscription/account ID, module version pins\n"
            "- `site.hcl` — region, location, site-specific values\n"
            "- `stack.hcl` — stack name, prefix, stack-specific inputs\n"
            "- `_envcommon/*.hcl` — shared module configs (source URL, dependencies, inputs)\n"
            "- `{component}/terragrunt.hcl` — component-specific overrides only"
        ),
        "component_config_pattern": (
            'include "root" {\n'
            '  path = find_in_parent_folders("root.hcl")\n'
            "}\n\n"
            'include "envcommon" {\n'
            '  path = "${dirname(find_in_parent_folders("subscription.hcl"))}/_envcommon/{module}.hcl"\n'
            "  expose = true\n"
            "  merge_strategy = \"deep\"\n"
            "}\n\n"
            "inputs = {\n"
            "  # component-specific overrides only\n"
            "}"
        ),
        "envcommon_template": (
            "locals {\n"
            '  sub_vars  = read_terragrunt_config(find_in_parent_folders("subscription.hcl"))\n'
            '  site_vars = read_terragrunt_config(find_in_parent_folders("site.hcl"))\n'
            '  stack_vars = read_terragrunt_config(find_in_parent_folders("stack.hcl"))\n'
            "}\n\n"
            'terraform {\n  source = "git::https://github.com/{org}/{module}?ref=${local.sub_vars.locals.module_versions.{module}}"\n}\n\n'
            "dependency \"{dep}\" {\n"
            '  config_path = "../{dep}"\n'
            "  mock_outputs = {\n"
            '    id   = "mock-id"\n'
            '    name = "mock-name"\n'
            "  }\n"
            "  mock_outputs_allowed_terraform_commands = [\"validate\", \"plan\"]\n"
            "}\n\n"
            "inputs = {\n"
            "  prefix   = local.stack_vars.locals.prefix\n"
            "  location = local.site_vars.locals.location\n"
            "}"
        ),
        "mock_outputs_example": (
            "dependency \"networking\" {\n"
            '  config_path = "../networking"\n'
            "  mock_outputs = {\n"
            '    vnet_id            = "mock-vnet-id"\n'
            '    subnet_ids         = { default = "mock-subnet-id" }\n'
            "  }\n"
            "  mock_outputs_allowed_terraform_commands = [\"validate\", \"plan\"]\n"
            "}"
        ),
        "site_config_template": (
            "locals {\n"
            '  location = "westeurope"\n'
            '  region   = "weu"\n'
            "}"
        ),
        "stack_config_template": (
            "locals {\n"
            '  stack_name = "platform"\n'
            '  prefix     = "${local.sub_vars.locals.env}-${local.stack_name}"\n'
            "}"
        ),
        "input_flow_diagram": (
            "subscription.hcl (versions, account)\n"
            "  └─► site.hcl (region, location)\n"
            "        └─► stack.hcl (prefix, stack name)\n"
            "              └─► _envcommon/*.hcl (source, deps, base inputs)\n"
            "                    └─► component/terragrunt.hcl (overrides)"
        ),
        "dependency_conventions": (
            "- Always declare dependencies explicitly with `dependency {}` blocks\n"
            "- Always include `mock_outputs` for plan-time compatibility\n"
            "- Set `mock_outputs_allowed_terraform_commands = [\"validate\", \"plan\"]`\n"
            "- Use relative `config_path` references (e.g. `../networking`)"
        ),
        "version_tag_location": "subscription.hcl → `locals.module_versions`",
        "version_tag_example": 'module_versions = {\n  tf-module-keyvault = "v1.2.0"\n  tf-module-network   = "v2.0.1"\n}',
    },
    "Terramate": {
        "tool_lower": "terramate",
        "validate_command": "terramate run terraform validate",
        "plan_command": "terramate run terraform plan",
        "plan_all_command": "terramate run terraform plan",
        "plan_single_command": "terramate run --stack . terraform plan",
        "graph_command": "terramate list --changed",
        "extra_run_flags": "",
        "envcommon_pattern": "globals.tm.hcl",
        "hierarchy_diagram": (
            "stacks/\n"
            "├── globals.tm.hcl              # global values\n"
            "└── {environment}/\n"
            "    ├── globals.tm.hcl          # env-level values\n"
            "    └── {stack}/\n"
            "        ├── stack.tm.hcl        # stack definition\n"
            "        └── main.tf             # Terraform config"
        ),
        "hierarchy_files_description": (
            "- `globals.tm.hcl` — global or environment-level values\n"
            "- `stack.tm.hcl` — stack definition (tags, description)\n"
            "- `generate_hcl` blocks — dynamically generate Terraform files"
        ),
        "component_config_pattern": (
            'stack {\n  name        = "{stack-name}"\n  description = "{description}"\n  tags        = ["{env}", "{component}"]\n}'
        ),
        "envcommon_template": 'globals {\n  prefix   = "{prefix}"\n  location = "{location}"\n}',
        "mock_outputs_example": "# Terramate uses data sources for cross-stack references",
        "site_config_template": 'globals {\n  location = "westeurope"\n}',
        "stack_config_template": 'globals {\n  stack_name = "platform"\n}',
        "input_flow_diagram": "globals.tm.hcl → env/globals.tm.hcl → stack/stack.tm.hcl → generate_hcl",
        "dependency_conventions": (
            "- Use `terramate.required_by` for explicit ordering\n"
            "- Reference outputs via `data` blocks or remote state"
        ),
        "version_tag_location": "globals.tm.hcl → `globals.module_versions`",
        "version_tag_example": 'module_versions = {\n  tf-module-keyvault = "v1.2.0"\n}',
    },
    "None": {
        "tool_lower": "terraform",
        "validate_command": "terraform validate",
        "plan_command": "terraform plan",
        "plan_all_command": "terraform plan",
        "plan_single_command": "terraform plan",
        "graph_command": "terraform graph",
        "extra_run_flags": "",
        "envcommon_pattern": "environments/",
        "hierarchy_diagram": (
            "environments/\n"
            "├── dev/\n"
            "│   └── main.tf\n"
            "├── staging/\n"
            "│   └── main.tf\n"
            "└── prod/\n"
            "    └── main.tf"
        ),
        "hierarchy_files_description": (
            "- `environments/{env}/main.tf` — per-environment root module\n"
            "- `modules/` — shared reusable modules"
        ),
        "component_config_pattern": (
            'module "{name}" {\n'
            '  source = "../../modules/{name}"\n'
            "  # inputs\n"
            "}"
        ),
        "envcommon_template": '# shared locals\nlocals {\n  prefix = "{prefix}"\n}',
        "mock_outputs_example": "# Use terraform_remote_state for cross-module references",
        "site_config_template": 'locals {\n  location = "us-east-1"\n}',
        "stack_config_template": 'locals {\n  prefix = "myapp-dev"\n}',
        "input_flow_diagram": "environments/{env}/main.tf → modules/{name}/",
        "dependency_conventions": (
            "- Use `terraform_remote_state` for cross-component references\n"
            "- Or use module composition within the same root"
        ),
        "version_tag_location": "versions.tf → `required_providers`",
        "version_tag_example": 'terraform {\n  required_providers {\n    azurerm = {\n      version = ">=4.0.0,<5.0.0"\n    }\n  }\n}',
    },
}

# ---------------------------------------------------------------------------
# CI/CD platform defaults
# ---------------------------------------------------------------------------

_CICD_DEFAULTS: dict[str, dict] = {
    "GitHub Actions": {
        "pipeline_apply_to": ".github/workflows/**/*.yml",
        "pipeline_dir": ".github/workflows",
        "auth_requirements": (
            "Use OIDC federation — no long-lived secrets in workflow files.\n"
            "Configure `permissions: id-token: write` and use the provider's official login action."
        ),
        "template_reference_pattern": (
            "Use reusable workflows (`workflow_call`) for plan/apply stages.\n"
            "Reference shared templates via `uses: {org}/{repo}/.github/workflows/{template}.yml@{ref}`."
        ),
        "pipeline_conventions": (
            "- Name: `{action}-{component}.yml` (e.g. `deploy-networking.yml`)\n"
            "- Two-stage: plan (on PR) → apply (on merge to main, with environment protection)\n"
            "- Use `concurrency:` to prevent parallel runs on the same stack"
        ),
        "standard_parameters": (
            "- `environment` — target environment name\n"
            "- `working_directory` — path to component/stack root\n"
            "- `terraform_version` — Terraform version to use"
        ),
    },
    "Azure DevOps": {
        "pipeline_apply_to": "**/pipelines/**/*.yml",
        "pipeline_dir": "pipelines",
        "auth_requirements": (
            "Use Service Connection with Managed Identity or Workload Identity Federation.\n"
            "Reference the service connection name via a pipeline variable or parameter."
        ),
        "template_reference_pattern": (
            "Use Azure DevOps pipeline templates for reuse.\n"
            "Reference shared templates via `template: templates/{name}.yml@{resource}`."
        ),
        "pipeline_conventions": (
            "- Name: `{action}-{component}.yml`\n"
            "- Two-stage: Plan (on PR) → Apply (on merge, with approval gate)\n"
            "- Use `dependsOn:` and `condition:` for stage gating"
        ),
        "standard_parameters": (
            "- `environment` — target environment name\n"
            "- `workingDirectory` — path to component/stack root\n"
            "- `terraformVersion` — Terraform version to use\n"
            "- `serviceConnection` — Azure service connection name"
        ),
    },
    "GitLab CI": {
        "pipeline_apply_to": "**/.gitlab-ci.yml",
        "pipeline_dir": ".",
        "auth_requirements": (
            "Use OIDC with GitLab CI/CD variables for cloud authentication.\n"
            "Set `id_tokens:` in the job to obtain a JWT for cloud provider login."
        ),
        "template_reference_pattern": (
            "Use GitLab CI `include:` for template reuse.\n"
            "Reference shared templates via `include: - project: {group}/{project}  file: {template}.yml`."
        ),
        "pipeline_conventions": (
            "- Stages: `plan` → `apply`\n"
            "- Use `environment:` keyword with manual approval for apply\n"
            "- Use `rules:` to control when each stage runs"
        ),
        "standard_parameters": (
            "- `TF_ENV` — target environment name\n"
            "- `TF_WORKING_DIR` — path to component/stack root\n"
            "- `TF_VERSION` — Terraform version to use"
        ),
    },
    "Atlantis": {
        "pipeline_apply_to": "atlantis.yaml",
        "pipeline_dir": ".",
        "auth_requirements": (
            "Atlantis uses server-side credentials. Configure provider auth in the Atlantis server environment.\n"
            "Use Atlantis `allowed_override_admins` for manual apply approval."
        ),
        "template_reference_pattern": (
            "Define workflows in `atlantis.yaml` at the repo root.\n"
            "Use custom `workflow:` blocks for non-standard plan/apply steps."
        ),
        "pipeline_conventions": (
            "- Define repos and workflows in `atlantis.yaml`\n"
            "- Plan runs automatically on PR; apply requires `atlantis apply` comment\n"
            "- Use `when_modified:` to scope plans to changed files"
        ),
        "standard_parameters": (
            "- `workspace` — Terraform workspace name\n"
            "- `dir` — path to Terraform root\n"
            "- `terraform_version` — Terraform version"
        ),
    },
}

# ---------------------------------------------------------------------------
# Auth pattern defaults
# ---------------------------------------------------------------------------

_AUTH_DEFAULTS: dict[str, str] = {
    "Managed Identity / OIDC": (
        "Azure: Use Managed Identity (for Azure-hosted runners) or OIDC federation "
        "(for GitHub Actions/GitLab CI). Configure `use_oidc = true` in the azurerm provider. "
        "No client secrets stored in pipelines."
    ),
    "IAM Roles via OIDC": (
        "AWS: Use IAM roles assumed via OIDC federation. Configure the AWS provider with "
        "`assume_role` and use the official `aws-actions/configure-aws-credentials` action. "
        "No access keys stored in pipelines."
    ),
    "Workload Identity Federation": (
        "GCP: Use Workload Identity Federation for keyless authentication from CI/CD. "
        "Configure `google-github-actions/auth` with the WIF provider and service account. "
        "No service account keys stored in pipelines."
    ),
    "Service Principal": (
        "Azure: Use a Service Principal with federated credentials (preferred) or client secret. "
        "Store credentials in pipeline secrets/variables, never in code."
    ),
    "Access Keys": (
        "WARNING: Prefer OIDC/role-based auth. If using access keys, store in secrets manager "
        "and rotate regularly. Never hardcode credentials in Terraform or pipeline files."
    ),
}


# ---------------------------------------------------------------------------
# Derived context builder
# ---------------------------------------------------------------------------


def build_context(answers: dict) -> dict:
    """Build the full ``{{PLACEHOLDER}}`` context dict from raw interview answers."""
    ctx: dict = dict(answers)

    cloud = answers.get("CLOUD_PROVIDER", "Azure")
    orch = answers.get("ORCHESTRATION_TOOL", "None")
    cicd = answers.get("CI_CD_PLATFORM", "GitHub Actions")
    org = answers.get("ORG", answers.get("COMPANY_NAME", "myorg"))
    module_prefix = answers.get("MODULE_PREFIX", "tf-module")
    auth = answers.get("AUTH_PATTERN", "")

    # ---- Cloud provider derived values -----
    cloud_defs = _CLOUD_PROVIDER_DEFAULTS.get(cloud, _CLOUD_PROVIDER_DEFAULTS["Azure"])
    ctx.setdefault("PROVIDER_NAME", cloud_defs["provider_name"])
    ctx.setdefault(
        "PROVIDER_VERSION_CONSTRAINTS",
        (
            f'terraform {{\n'
            f'  required_providers {{\n'
            f'    {cloud_defs["provider_name"]} = {{\n'
            f'      source  = "hashicorp/{cloud_defs["provider_name"]}"\n'
            f'      version = "{cloud_defs["provider_version_constraints"]}"\n'
            f'    }}\n'
            f'  }}\n'
            f'}}'
        ),
    )
    ctx.setdefault(
        "PROVIDER_BLOCK",
        (
            f'{cloud_defs["provider_name"]} = {{\n'
            f'  source  = "hashicorp/{cloud_defs["provider_name"]}"\n'
            f'  version = "{cloud_defs["provider_version_constraints"]}"\n'
            f"}}"
        ),
    )
    ctx.setdefault("PROVIDER_RESOURCE_EXAMPLE", cloud_defs["provider_resource_example"])
    ctx.setdefault("PROVIDER_RESOURCE", cloud_defs["provider_resource_example"])
    ctx.setdefault("LOCATION_ATTRIBUTE", cloud_defs["location_attribute"])
    ctx.setdefault("RESOURCE_GROUP_ATTRIBUTE", cloud_defs["resource_group_attribute"])
    ctx.setdefault("PRIVATE_ENDPOINT_PATTERN", cloud_defs["private_endpoint_pattern"])
    ctx.setdefault("STANDARD_VARIABLES", cloud_defs["standard_variables"])
    ctx.setdefault(
        "TAG_MERGE_PATTERN",
        "merge(var.env_default_tags, var.tags)"
        if cloud == "Azure"
        else "merge(var.default_tags, var.tags)"
        if cloud == "AWS"
        else "merge(var.default_labels, var.labels)",
    )
    ctx.setdefault(
        "TAG_MERGE_LOCAL",
        "tags = " + ctx["TAG_MERGE_PATTERN"]
        if cloud != "GCP"
        else "labels = " + ctx["TAG_MERGE_PATTERN"],
    )
    ctx.setdefault(
        "TAG_ATTRIBUTE",
        "labels" if cloud == "GCP" else "tags",
    )
    ctx.setdefault(
        "TAG_LOCAL_REF",
        "local.labels" if cloud == "GCP" else "local.tags",
    )

    # ---- Orchestration derived values ----
    orch_key = orch if orch in _ORCHESTRATION_DEFAULTS else "None"
    orch_defs = _ORCHESTRATION_DEFAULTS[orch_key]
    ctx.setdefault("ORCHESTRATION_TOOL_LOWER", orch_defs["tool_lower"])
    ctx.setdefault("VALIDATE_COMMAND", orch_defs["validate_command"])
    ctx.setdefault("PLAN_COMMAND", orch_defs["plan_command"])
    ctx.setdefault("PLAN_ALL_COMMAND", orch_defs["plan_all_command"])
    ctx.setdefault("PLAN_SINGLE_COMMAND", orch_defs["plan_single_command"])
    ctx.setdefault("GRAPH_COMMAND", orch_defs["graph_command"])
    ctx.setdefault("EXTRA_RUN_FLAGS", orch_defs["extra_run_flags"])
    ctx.setdefault("ENVCOMMON_PATTERN", orch_defs["envcommon_pattern"])
    ctx.setdefault("HIERARCHY_DIAGRAM", orch_defs["hierarchy_diagram"])
    ctx.setdefault(
        "HIERARCHY_FILES_DESCRIPTION", orch_defs["hierarchy_files_description"]
    )
    ctx.setdefault("COMPONENT_CONFIG_PATTERN", orch_defs["component_config_pattern"])
    ctx.setdefault("COMPONENT_CONFIG_TEMPLATE", orch_defs["component_config_pattern"])
    ctx.setdefault("ENVCOMMON_TEMPLATE", orch_defs["envcommon_template"])
    ctx.setdefault("MOCK_OUTPUTS_EXAMPLE", orch_defs["mock_outputs_example"])
    ctx.setdefault("SITE_CONFIG_TEMPLATE", orch_defs["site_config_template"])
    ctx.setdefault("STACK_CONFIG_TEMPLATE", orch_defs["stack_config_template"])
    ctx.setdefault("INPUT_FLOW_DIAGRAM", orch_defs["input_flow_diagram"])
    ctx.setdefault("DEPENDENCY_CONVENTIONS", orch_defs["dependency_conventions"])
    ctx.setdefault("VERSION_TAG_LOCATION", orch_defs["version_tag_location"])
    ctx.setdefault("VERSION_TAG_EXAMPLE", orch_defs["version_tag_example"])

    # ---- CI/CD derived values ----
    cicd_key = cicd if cicd in _CICD_DEFAULTS else "GitHub Actions"
    cicd_defs = _CICD_DEFAULTS[cicd_key]
    ctx.setdefault("PIPELINE_APPLY_TO", cicd_defs["pipeline_apply_to"])
    ctx.setdefault("PIPELINE_DIR", cicd_defs["pipeline_dir"])
    ctx.setdefault("AUTH_REQUIREMENTS", cicd_defs["auth_requirements"])
    ctx.setdefault("TEMPLATE_REFERENCE_PATTERN", cicd_defs["template_reference_pattern"])
    ctx.setdefault("PIPELINE_CONVENTIONS", cicd_defs["pipeline_conventions"])
    ctx.setdefault("PIPELINE_CONVENTIONS_LIST", cicd_defs["pipeline_conventions"])
    ctx.setdefault("STANDARD_PARAMETERS", cicd_defs["standard_parameters"])
    ctx.setdefault("STANDARD_PARAMETERS_LIST", cicd_defs["standard_parameters"])
    ctx.setdefault(
        "PIPELINE_TEMPLATES_REPO",
        f"github.com/{org}/pipeline-templates",
    )

    # ---- Auth derived values ----
    auth_key = next((k for k in _AUTH_DEFAULTS if auth and k.lower() in auth.lower()), None)
    if auth_key:
        ctx.setdefault("AUTH_PATTERN", _AUTH_DEFAULTS[auth_key])
    else:
        ctx.setdefault(
            "AUTH_PATTERN",
            auth or _AUTH_DEFAULTS.get(
                cloud_defs.get("auth_pattern", ""),
                "Use identity-based authentication (OIDC/Managed Identity). No hardcoded secrets.",
            ),
        )

    # ---- Module source derived ----
    ctx.setdefault(
        "MODULE_SOURCE_PATTERN",
        f"git::https://github.com/{org}/{module_prefix}-{{name}}?ref={{tag}}",
    )
    ctx.setdefault("MODULE_SOURCE_CONVENTION", ctx["MODULE_SOURCE_PATTERN"])
    ctx.setdefault("ORG", org)
    ctx.setdefault("PROJECT", org)

    # ---- Naming & testing derived ----
    ctx.setdefault(
        "NAMING_PATTERN_HCL",
        f'name = "${{var.prefix}}-${{local.resource_abbreviation}}-${{local.suffix}}"',
    )
    ctx.setdefault(
        "NAMING_LOCALS",
        (
            "name = substr(\n"
            '  "${var.prefix}-${local.resource_abbreviation}-${local.suffix}",\n'
            "  0, 24\n"
            ")"
        ),
    )
    ctx.setdefault("RESOURCE_IDENTIFIER", "default")
    ctx.setdefault("COMMON_VARS_FILE", "common.variables.tf")
    ctx.setdefault(
        "DATA_SOURCE_OVERRIDE",
        (
            'override_data {\n'
            '  target = data.{provider}_{resource}.current\n'
            '  values = {\n'
            '    id = "/subscriptions/00000000-0000-0000-0000-000000000000"\n'
            '  }\n'
            '}'
        ).replace("{provider}", ctx.get("PROVIDER_NAME", "azurerm")),
    )
    ctx.setdefault(
        "TEST_STANDARD_VARIABLES",
        (
            "variables {\n"
            '  prefix   = "test-auto"\n'
            '  location = "westeurope"\n'
            "}"
        ),
    )
    ctx.setdefault("EXPECTED_NAME_PATTERN", "test-auto-{resource_abbreviation}-mysuffix")
    ctx.setdefault("OPTIONAL_FEATURES", "private endpoints, diagnostics settings, RBAC assignments")
    ctx.setdefault("VARIABLE_GOTCHAS", "Use `optional(type, default)` for object attributes (Terraform 1.3+)")

    # ---- Pipeline code snippets (minimal defaults) ----
    ctx.setdefault(
        "SINGLE_COMPONENT_PIPELINE",
        _single_component_pipeline(cicd, org, module_prefix),
    )
    ctx.setdefault("STACK_PIPELINE", _stack_pipeline(cicd, orch))
    ctx.setdefault("DRIFT_PIPELINE", _drift_pipeline(cicd, orch))

    # ---- Environment hierarchy ----
    ctx.setdefault(
        "ENVIRONMENT_HIERARCHY",
        _environment_hierarchy(orch),
    )

    # ---- Tag / naming strategy (user-provided, fall back to cloud default) ----
    ctx.setdefault("TAG_STRATEGY", cloud_defs["tag_strategy"])
    ctx.setdefault("NAMING_PATTERN", cloud_defs["naming_pattern"])

    return ctx


# ---------------------------------------------------------------------------
# Pipeline snippet generators
# ---------------------------------------------------------------------------


def _single_component_pipeline(cicd: str, org: str, module_prefix: str) -> str:
    if "GitHub" in cicd:
        return (
            "name: plan-apply-{component}\n"
            "on:\n"
            "  push:\n"
            "    branches: [main]\n"
            "    paths:\n"
            "      - 'infrastructure-config/**/{component}/**'\n"
            "  pull_request:\n"
            "    paths:\n"
            "      - 'infrastructure-config/**/{component}/**'\n\n"
            "jobs:\n"
            "  plan:\n"
            "    uses: {org}/pipeline-templates/.github/workflows/tf-plan.yml@main\n"
            "    with:\n"
            "      working_directory: infrastructure-config/dev/platform/{component}\n"
            "    permissions:\n"
            "      id-token: write\n"
            "      contents: read\n"
            "  apply:\n"
            "    needs: plan\n"
            "    if: github.ref == 'refs/heads/main'\n"
            "    uses: {org}/pipeline-templates/.github/workflows/tf-apply.yml@main\n"
            "    with:\n"
            "      working_directory: infrastructure-config/dev/platform/{component}\n"
            "    permissions:\n"
            "      id-token: write\n"
            "      contents: read\n"
            "    environment: production\n"
        ).replace("{org}", org)
    if "Azure DevOps" in cicd:
        return (
            "stages:\n"
            "- stage: Plan\n"
            "  jobs:\n"
            "  - template: templates/tf-plan.yml\n"
            "    parameters:\n"
            "      workingDirectory: infrastructure-config/dev/platform/{component}\n"
            "- stage: Apply\n"
            "  dependsOn: Plan\n"
            "  condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))\n"
            "  jobs:\n"
            "  - template: templates/tf-apply.yml\n"
            "    parameters:\n"
            "      workingDirectory: infrastructure-config/dev/platform/{component}\n"
        )
    return "# Define your plan → apply pipeline stages here"


def _stack_pipeline(cicd: str, orch: str) -> str:
    tool = _ORCHESTRATION_DEFAULTS.get(orch, _ORCHESTRATION_DEFAULTS["None"])["tool_lower"]
    if "GitHub" in cicd:
        if tool == "terraform":
            plan_cmd = "terraform plan"
            apply_cmd = "terraform apply --auto-approve"
        else:
            plan_cmd = f"{tool} run-all plan"
            apply_cmd = f"{tool} run-all apply --auto-approve"
        return (
            "name: plan-apply-stack\n"
            "on:\n"
            "  push:\n"
            "    branches: [main]\n"
            "    paths:\n"
            "      - 'infrastructure-config/**'\n\n"
            "jobs:\n"
            "  plan:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            f"      - run: {plan_cmd}\n"
            "        working-directory: infrastructure-config/dev/platform\n"
            "  apply:\n"
            "    needs: plan\n"
            "    if: github.ref == 'refs/heads/main'\n"
            "    environment: production\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            f"      - run: {apply_cmd}\n"
            "        working-directory: infrastructure-config/dev/platform\n"
        )
    return "# Define your stack-level plan → apply pipeline here"


def _drift_pipeline(cicd: str, orch: str) -> str:
    tool = _ORCHESTRATION_DEFAULTS.get(orch, _ORCHESTRATION_DEFAULTS["None"])["tool_lower"]
    if "GitHub" in cicd:
        if tool == "terraform":
            plan_cmd = "terraform plan --detailed-exitcode"
        else:
            plan_cmd = f"{tool} run-all plan --detailed-exitcode"
        return (
            "name: drift-detection\n"
            "on:\n"
            "  schedule:\n"
            "    - cron: '0 6 * * 1-5'  # Weekdays at 06:00 UTC\n\n"
            "jobs:\n"
            "  drift:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            f"      - run: {plan_cmd}\n"
            "        working-directory: infrastructure-config\n"
            "        continue-on-error: true\n"
            "      - name: Notify on drift\n"
            "        if: failure()\n"
            "        run: echo 'Drift detected — review plan output'\n"
        )
    return "# Define your drift detection pipeline here (scheduled plan run)"


def _environment_hierarchy(orch: str) -> str:
    if orch == "Terragrunt":
        return (
            "config/{environment}/{region}/{stack}/{component}/terragrunt.hcl\n\n"
            "Hierarchy files:\n"
            "- subscription.hcl — account/subscription ID, module versions\n"
            "- site.hcl — region, location\n"
            "- stack.hcl — stack name, prefix\n"
            "- _envcommon/*.hcl — shared module configs"
        )
    if orch == "Terramate":
        return (
            "stacks/{environment}/{stack}/stack.tm.hcl\n\n"
            "Global values flow through globals.tm.hcl at each directory level."
        )
    return (
        "environments/{env}/main.tf — per-environment root module\n"
        "modules/ — shared reusable modules"
    )


# ---------------------------------------------------------------------------
# Interactive interview
# ---------------------------------------------------------------------------


def _prompt(
    message: str,
    default: Optional[str] = None,
    choices: Optional[list[str]] = None,
) -> str:
    """Prompt the user, optionally restricting to *choices*."""
    if choices:
        choices_str = "/".join(choices)
        msg = f"{message} [{choices_str}]"
        default_val = default or choices[0]
        while True:
            val = click.prompt(msg, default=default_val)
            if val in choices:
                return val
            click.echo(f"  Please choose one of: {', '.join(choices)}", err=True)
    return click.prompt(message, default=default or "")


def run_interview(
    discovery: DiscoveryResult,
    *,
    non_interactive: bool = False,
    overrides: Optional[dict] = None,
) -> dict:
    """Run the bootstrap interview.

    Parameters
    ----------
    discovery:
        Results from :func:`~bootstrap_iac.discovery.scan_workspace`.
    non_interactive:
        When *True* only use discovered defaults and *overrides* — never
        prompt the user.
    overrides:
        Pre-set values supplied via CLI flags (take precedence over
        discovered defaults and prompts).

    Returns
    -------
    dict
        Raw interview answers (keys match placeholder names).
    """
    overrides = overrides or {}
    answers: dict = {}

    def _get(key: str, prompt_msg: str, default: Optional[str], choices=None) -> str:
        if key in overrides and overrides[key]:
            return overrides[key]
        if non_interactive:
            return default or ""
        return _prompt(prompt_msg, default=default, choices=choices)

    # 1. Company/org name
    answers["COMPANY_NAME"] = _get(
        "COMPANY_NAME",
        "Company/organisation name",
        discovery.org_name or "MyOrg",
    )

    # 2. Cloud provider
    answers["CLOUD_PROVIDER"] = _get(
        "CLOUD_PROVIDER",
        "Primary cloud provider",
        discovery.cloud_provider or "Azure",
        choices=["Azure", "AWS", "GCP"],
    )

    # 3. Module prefix
    answers["MODULE_PREFIX"] = _get(
        "MODULE_PREFIX",
        "Module directory prefix (e.g. tf-module, terraform-aws)",
        discovery.module_prefix or "tf-module",
    )

    # 4. Orchestration tool
    answers["ORCHESTRATION_TOOL"] = _get(
        "ORCHESTRATION_TOOL",
        "Orchestration tool",
        discovery.orchestration_tool or "None",
        choices=["Terragrunt", "Terramate", "None"],
    )

    # 5. Orchestration directory (only if using an orchestration tool)
    if answers["ORCHESTRATION_TOOL"] != "None":
        answers["ORCHESTRATION_DIR"] = _get(
            "ORCHESTRATION_DIR",
            "Directory containing orchestration configs",
            discovery.orchestration_dir or "infrastructure-config",
        )
    else:
        answers["ORCHESTRATION_DIR"] = overrides.get("ORCHESTRATION_DIR", ".")

    # 6. CI/CD platform
    answers["CI_CD_PLATFORM"] = _get(
        "CI_CD_PLATFORM",
        "CI/CD platform",
        discovery.ci_cd_platform or "GitHub Actions",
        choices=["GitHub Actions", "Azure DevOps", "GitLab CI", "Atlantis"],
    )

    # 7. Auth pattern
    cloud = answers["CLOUD_PROVIDER"]
    default_auth = discovery.auth_pattern or _CLOUD_PROVIDER_DEFAULTS.get(
        cloud, {}
    ).get("auth_pattern", "OIDC")
    answers["AUTH_PATTERN"] = _get(
        "AUTH_PATTERN",
        "Authentication pattern",
        default_auth,
    )

    # 8. State backend
    default_backend = discovery.state_backend or _CLOUD_PROVIDER_DEFAULTS.get(
        cloud, {}
    ).get("state_backend", "Remote")
    answers["STATE_BACKEND"] = _get(
        "STATE_BACKEND",
        "Terraform state backend",
        default_backend,
    )

    # 9. Naming convention
    default_naming = discovery.naming_pattern or _CLOUD_PROVIDER_DEFAULTS.get(
        cloud, {}
    ).get("naming_pattern", "{prefix}-{resource_type}-{suffix}")
    answers["NAMING_PATTERN"] = _get(
        "NAMING_PATTERN",
        "Resource naming pattern",
        default_naming,
    )

    # 10. Tag/label strategy
    default_tag = discovery.tag_strategy or _CLOUD_PROVIDER_DEFAULTS.get(
        cloud, {}
    ).get(
        "tag_strategy",
        "merge(var.default_tags, var.tags)",
    )
    answers["TAG_STRATEGY"] = _get(
        "TAG_STRATEGY",
        "Tagging/labeling strategy (HCL expression or description)",
        default_tag,
    )

    # 11. Standard variables (cross-module)
    default_vars = _CLOUD_PROVIDER_DEFAULTS.get(cloud, {}).get("standard_variables", "")
    answers["STANDARD_VARIABLES"] = _get(
        "STANDARD_VARIABLES",
        "Standard cross-module variables (comma-separated or freeform)",
        default_vars,
    )

    # 12. Target tool(s)
    answers["TARGET"] = _get(
        "TARGET",
        "Generate output for",
        "both",
        choices=["copilot", "claude", "both"],
    )

    # 13. Org name for module source URLs
    answers["ORG"] = _get(
        "ORG",
        "GitHub/ADO org name (used in module source URLs)",
        discovery.org_name or answers["COMPANY_NAME"].lower().replace(" ", "-"),
    )

    return answers
