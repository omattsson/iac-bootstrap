"""Cloud, orchestration, and CI/CD specific defaults for placeholder generation."""

from __future__ import annotations

CLOUD_DEFAULTS: dict[str, dict] = {
    "Azure": {
        "provider_name": "azurerm",
        "provider_resource": "azurerm_resource_group",
        "provider_resource_example": "azurerm_key_vault.default",
        "location_attribute": "location = var.location",
        "resource_group_attribute": "resource_group_name = var.resource_group_name",
        "state_backend": "Azure Blob Storage",
        "provider_version_constraints": ">=4.0.0,<5.0",
        "standard_variables_default": (
            "- `prefix` — Resource name prefix (e.g., `app-weu-dev`)\n"
            "- `location` — Azure region (default: `westeurope`)\n"
            "- `resource_group_name` — Target resource group\n"
            "- `tags` — Additional tags (`map(string)`)\n"
            "- `env_default_tags` — Default tags from orchestration layer"
        ),
        "naming_pattern_default": "`{prefix}-{resource_abbreviation}-{suffix}`",
        "tag_merge_pattern": "merge(var.env_default_tags, var.tags)",
        "private_endpoint_pattern": (
            "```hcl\n"
            "resource \"azurerm_private_endpoint\" \"default\" {\n"
            "  for_each = var.private_endpoints\n"
            "  name     = \"${local.name}-pe-${each.key}\"\n"
            "}\n"
            "```"
        ),
        "data_source_override": (
            "override_data {\n"
            '  target = data.azurerm_subscription.current\n'
            "  values = {\n"
            '    subscription_id = "00000000-0000-0000-0000-000000000000"\n'
            "  }\n"
            "}"
        ),
        "optional_features": "private endpoints, diagnostic settings, RBAC role assignments",
        "variable_gotchas": (
            "- `location` must match the resource group's location\n"
            "- `resource_group_name` must already exist (use data source or dependency)\n"
            "- Key Vault names are globally unique and max 24 characters"
        ),
    },
    "AWS": {
        "provider_name": "aws",
        "provider_resource": "aws_s3_bucket",
        "provider_resource_example": "aws_s3_bucket.default",
        "location_attribute": "# AWS resources use region from the provider configuration",
        "resource_group_attribute": "# AWS uses tags for grouping, not resource groups",
        "state_backend": "S3 + DynamoDB",
        "provider_version_constraints": ">=5.0.0,<6.0",
        "standard_variables_default": (
            "- `prefix` — Resource name prefix\n"
            "- `region` — AWS region (e.g., `us-east-1`)\n"
            "- `tags` — Additional tags (`map(string)`)\n"
            "- `default_tags` — Default tags from orchestration layer"
        ),
        "naming_pattern_default": "`{prefix}-{resource_type}-{suffix}`",
        "tag_merge_pattern": "merge(var.default_tags, var.tags)",
        "private_endpoint_pattern": (
            "```hcl\n"
            "resource \"aws_vpc_endpoint\" \"default\" {\n"
            "  for_each     = var.vpc_endpoints\n"
            "  service_name = each.value.service_name\n"
            "}\n"
            "```"
        ),
        "data_source_override": (
            "override_data {\n"
            "  target = data.aws_caller_identity.current\n"
            "  values = {\n"
            '    account_id = "123456789012"\n'
            "  }\n"
            "}"
        ),
        "optional_features": "VPC endpoints, S3 bucket policies, IAM roles, KMS encryption",
        "variable_gotchas": (
            "- S3 bucket names are globally unique\n"
            "- IAM ARNs include account ID — use data sources, not hardcoded values\n"
            "- KMS key ARNs vary by region"
        ),
    },
    "GCP": {
        "provider_name": "google",
        "provider_resource": "google_storage_bucket",
        "provider_resource_example": "google_storage_bucket.default",
        "location_attribute": "location = var.location",
        "resource_group_attribute": "project = var.project",
        "state_backend": "GCS",
        "provider_version_constraints": ">=5.0.0,<6.0",
        "standard_variables_default": (
            "- `project` — GCP project ID\n"
            "- `location` — GCP region or multi-region\n"
            "- `prefix` — Resource name prefix\n"
            "- `labels` — Default labels (`map(string)`)\n"
            "- `extra_labels` — Additional labels from orchestration layer"
        ),
        "naming_pattern_default": "`{prefix}-{resource_type}-{suffix}`",
        "tag_merge_pattern": "merge(var.labels, var.extra_labels)",
        "private_endpoint_pattern": (
            "```hcl\n"
            "resource \"google_compute_global_address\" \"private\" {\n"
            "  for_each      = var.private_service_connects\n"
            "  purpose       = \"VPC_PEERING\"\n"
            "  address_type  = \"INTERNAL\"\n"
            "}\n"
            "```"
        ),
        "data_source_override": (
            "override_data {\n"
            "  target = data.google_project.current\n"
            "  values = {\n"
            '    project_id = "my-project-id"\n'
            "  }\n"
            "}"
        ),
        "optional_features": "VPC Service Controls, Private Service Connect, IAM bindings, CMEK",
        "variable_gotchas": (
            "- GCS bucket names are globally unique\n"
            "- Project IDs are immutable after creation\n"
            "- Service account emails follow a fixed pattern"
        ),
    },
}

ORCHESTRATION_DEFAULTS: dict[str, dict] = {
    "Terragrunt": {
        "lower": "terragrunt",
        "validate_command": "terragrunt validate",
        "plan_command": "terragrunt plan",
        "plan_all_command": "terragrunt run-all plan",
        "plan_single_command": "terragrunt plan",
        "graph_command": "terragrunt graph-dependencies",
        "extra_run_flags": "--non-interactive --terragrunt-non-interactive",
        "envcommon_pattern": "_envcommon/*.hcl",
        "environment_hierarchy": (
            "```\n"
            "config/{environment}/{site}/{stack}/{component}/terragrunt.hcl\n"
            "```\n"
            "- `subscription.hcl` — Account/subscription ID, module versions\n"
            "- `site.hcl` — Region, location\n"
            "- `stack.hcl` — Stack name, prefix\n"
            "- `_envcommon/*.hcl` — Shared module configs with dependencies and inputs"
        ),
        "hierarchy_diagram": (
            "```\n"
            "config/\n"
            "├── subscription.hcl          # Account-level config\n"
            "├── dev/\n"
            "│   ├── site.hcl              # Region config\n"
            "│   └── app-stack/\n"
            "│       ├── stack.hcl         # Stack config\n"
            "│       └── keyvault/\n"
            "│           └── terragrunt.hcl\n"
            "├── _envcommon/\n"
            "│   └── keyvault.hcl          # Shared module config\n"
            "└── prod/\n"
            "    └── ...\n"
            "```"
        ),
        "hierarchy_files_description": (
            "- `subscription.hcl` — subscription/account IDs, module version tags\n"
            "- `site.hcl` — region, location, environment name\n"
            "- `stack.hcl` — stack name, prefix, shared inputs\n"
            "- `_envcommon/*.hcl` — module configs shared across environments\n"
            "- `{component}/terragrunt.hcl` — component-specific overrides and includes"
        ),
        "input_flow_diagram": (
            "```\n"
            "subscription.hcl (subscription_id, module_tags)\n"
            "    └── site.hcl (location, environment)\n"
            "            └── stack.hcl (prefix, stack_name)\n"
            "                    └── _envcommon/module.hcl (source, dependencies, inputs)\n"
            "                            └── component/terragrunt.hcl (include + overrides)\n"
            "```"
        ),
        "component_config_pattern": (
            "```hcl\n"
            "include \"root\" {\n"
            '  path = find_in_parent_folders("subscription.hcl")\n'
            "}\n\n"
            "include \"envcommon\" {\n"
            '  path = "${dirname(find_in_parent_folders("subscription.hcl"))}/_envcommon/module-name.hcl"\n'
            "  expose = true\n"
            "}\n"
            "```"
        ),
        "envcommon_template": (
            "```hcl\n"
            "locals {\n"
            '  subscription_vars = read_terragrunt_config(find_in_parent_folders("subscription.hcl"))\n'
            '  site_vars         = read_terragrunt_config(find_in_parent_folders("site.hcl"))\n'
            '  stack_vars        = read_terragrunt_config(find_in_parent_folders("stack.hcl"))\n\n'
            "  module_version = local.subscription_vars.locals.module_tags[\"module-name\"]\n"
            "}\n\n"
            "terraform {\n"
            "  source = \"${local.base_source_url}?ref=${local.module_version}\"\n"
            "}\n"
            "```"
        ),
        "mock_outputs_example": (
            "```hcl\n"
            "dependency \"keyvault\" {\n"
            '  config_path = "../keyvault"\n'
            "  mock_outputs = {\n"
            '    name = "mock-kv-name"\n'
            '    id   = "/subscriptions/00000000/resourceGroups/mock-rg/providers/Microsoft.KeyVault/vaults/mock-kv"\n'
            "  }\n"
            "  mock_outputs_allowed_terraform_commands = [\"validate\", \"plan\"]\n"
            "}\n"
            "```"
        ),
        "dependency_conventions": (
            "- Always provide `mock_outputs` for `validate` and `plan` commands\n"
            "- Mock output values must match the shape of actual outputs\n"
            "- Use descriptive keys — `mock-{resource}-name` pattern\n"
            "- Never use empty strings or zeros as mocks if the real output would be non-empty"
        ),
        "version_tag_location_default": "`subscription.hcl` → `module_tags` local",
    },
    "Terramate": {
        "lower": "terramate",
        "validate_command": "terramate run terraform validate",
        "plan_command": "terramate run terraform plan",
        "plan_all_command": "terramate run terraform plan",
        "plan_single_command": "terramate run --changed terraform plan",
        "graph_command": "terramate list --changed",
        "extra_run_flags": "--changed",
        "envcommon_pattern": "stacks/_base/*.tm.hcl",
        "environment_hierarchy": (
            "```\n"
            "stacks/{environment}/{stack}/\n"
            "```\n"
            "- `globals.tm.hcl` — Shared globals (region, prefix, tags)\n"
            "- `_base/*.tm.hcl` — Base stack configurations\n"
            "- `{stack}/stack.tm.hcl` — Stack definition with metadata"
        ),
        "hierarchy_diagram": (
            "```\n"
            "stacks/\n"
            "├── globals.tm.hcl          # Workspace globals\n"
            "├── dev/\n"
            "│   ├── globals.tm.hcl      # Environment globals\n"
            "│   └── app-stack/\n"
            "│       ├── stack.tm.hcl\n"
            "│       └── main.tf\n"
            "└── prod/\n"
            "    └── ...\n"
            "```"
        ),
        "hierarchy_files_description": (
            "- `globals.tm.hcl` — workspace-level globals (org, provider config)\n"
            "- `{env}/globals.tm.hcl` — environment globals (region, prefix)\n"
            "- `{stack}/stack.tm.hcl` — stack metadata and overrides\n"
            "- `{stack}/main.tf` — Terraform configuration for the stack"
        ),
        "input_flow_diagram": (
            "```\n"
            "globals.tm.hcl (org_name, provider)\n"
            "    └── {env}/globals.tm.hcl (region, environment)\n"
            "            └── {stack}/stack.tm.hcl (stack_name, overrides)\n"
            "                    └── {stack}/main.tf (uses global.{key})\n"
            "```"
        ),
        "component_config_pattern": (
            "```hcl\n"
            "# stack.tm.hcl\n"
            "stack {\n"
            '  name        = "my-stack"\n'
            '  description = "Manages my resource"\n'
            "  tags        = [\"terraform\", \"azure\"]\n"
            "}\n"
            "```"
        ),
        "envcommon_template": (
            "```hcl\n"
            "# globals.tm.hcl\n"
            "globals {\n"
            '  environment = "dev"\n'
            '  region      = "westeurope"\n'
            '  prefix      = "app-weu-dev"\n'
            "}\n"
            "```"
        ),
        "mock_outputs_example": (
            "```hcl\n"
            "# Reference outputs from another stack\n"
            "data \"terraform_remote_state\" \"keyvault\" {\n"
            '  backend = "azurerm"\n'
            "  config = {\n"
            '    resource_group_name  = global.state_resource_group\n'
            '    storage_account_name = global.state_storage_account\n'
            '    container_name       = "tfstate"\n'
            '    key                  = "keyvault.tfstate"\n'
            "  }\n"
            "}\n"
            "```"
        ),
        "dependency_conventions": (
            "- Use `terraform_remote_state` data sources for cross-stack dependencies\n"
            "- Store remote state config in globals for DRY reference\n"
            "- Use `--changed` flag to only plan/apply changed stacks"
        ),
        "version_tag_location_default": "`globals.tm.hcl` → `module_version` global",
    },
    "None": {
        "lower": "terraform",
        "validate_command": "terraform validate",
        "plan_command": "terraform plan",
        "plan_all_command": "terraform plan",
        "plan_single_command": "terraform plan",
        "graph_command": "terraform graph",
        "extra_run_flags": "",
        "envcommon_pattern": "modules/",
        "environment_hierarchy": (
            "```\n"
            "environments/{environment}/\n"
            "```\n"
            "- `main.tf` — Root module calling shared modules\n"
            "- `variables.tf` — Environment-specific variables\n"
            "- `terraform.tfvars` — Environment variable values"
        ),
        "hierarchy_diagram": (
            "```\n"
            "environments/\n"
            "├── dev/\n"
            "│   ├── main.tf\n"
            "│   └── terraform.tfvars\n"
            "├── staging/\n"
            "│   └── ...\n"
            "└── prod/\n"
            "    └── ...\n"
            "modules/\n"
            "├── networking/\n"
            "└── compute/\n"
            "```"
        ),
        "hierarchy_files_description": (
            "- `environments/{env}/main.tf` — root module for each environment\n"
            "- `environments/{env}/terraform.tfvars` — environment variable values\n"
            "- `modules/{name}/` — shared reusable modules"
        ),
        "input_flow_diagram": (
            "```\n"
            "terraform.tfvars (environment-specific values)\n"
            "    └── main.tf (root module calling child modules)\n"
            "            └── modules/{name}/ (reusable module)\n"
            "```"
        ),
        "component_config_pattern": (
            "```hcl\n"
            "module \"keyvault\" {\n"
            "  source = \"../../modules/keyvault\"\n\n"
            "  prefix              = var.prefix\n"
            "  location            = var.location\n"
            "  resource_group_name = var.resource_group_name\n"
            "  tags                = var.tags\n"
            "}\n"
            "```"
        ),
        "envcommon_template": (
            "```hcl\n"
            "# terraform.tfvars\n"
            'environment         = "dev"\n'
            'prefix              = "app-weu-dev"\n'
            'location            = "westeurope"\n'
            'resource_group_name = "rg-app-dev"\n'
            "```"
        ),
        "mock_outputs_example": (
            "```hcl\n"
            "# Use output references across root modules via remote state\n"
            "data \"terraform_remote_state\" \"networking\" {\n"
            '  backend = "s3"\n'
            "  config = {\n"
            '    bucket = var.state_bucket\n'
            '    key    = "networking/terraform.tfstate"\n'
            "  }\n"
            "}\n"
            "```"
        ),
        "dependency_conventions": (
            "- Use `terraform_remote_state` data sources for cross-environment dependencies\n"
            "- Keep modules small and single-purpose\n"
            "- Pin module versions in root `main.tf` source references"
        ),
        "version_tag_location_default": "`main.tf` → module source `?ref=` parameter",
    },
}

CICD_DEFAULTS: dict[str, dict] = {
    "GitHub Actions": {
        "pipeline_dir": ".github/workflows",
        "pipeline_apply_to": "**/.github/workflows/**/*.yml",
        "template_reference_pattern": (
            "Store reusable workflow files in `.github/workflows/` and reference with\n"
            "`uses: ./.github/workflows/reusable-workflow.yml`."
        ),
        "standard_parameters": (
            "```yaml\n"
            "on:\n"
            "  workflow_call:\n"
            "    inputs:\n"
            "      environment:\n"
            "        type: string\n"
            "        required: true\n"
            "      working_directory:\n"
            "        type: string\n"
            "        default: '.'\n"
            "```"
        ),
        "standard_parameters_list": (
            "- `environment` — target environment name (dev/staging/prod)\n"
            "- `working_directory` — path to the component/stack\n"
            "- `terraform_version` — Terraform version to use"
        ),
        "pipeline_conventions": (
            "- Use reusable workflows (`workflow_call`) for plan and apply stages\n"
            "- Plan on all pushes and pull requests\n"
            "- Apply only on pushes to protected branches with required approvals\n"
            "- Use environment protection rules for prod deployments\n"
            "- Cache `.terraform` directories and provider binaries"
        ),
        "pipeline_conventions_list": (
            "- Reusable workflows in `.github/workflows/`\n"
            "- Plan stage: triggered on `push` and `pull_request`\n"
            "- Apply stage: triggered on `push` to `main`/`master` with environment gates\n"
            "- Drift detection: scheduled `cron` workflow (daily)\n"
            "- Use `actions/checkout` and `hashicorp/setup-terraform`"
        ),
    },
    "Azure DevOps": {
        "pipeline_dir": "pipelines",
        "pipeline_apply_to": "**/pipelines/**/*.yml",
        "template_reference_pattern": (
            "Store pipeline templates in `pipelines/templates/` and reference with\n"
            "`template: templates/plan.yml@self`."
        ),
        "standard_parameters": (
            "```yaml\n"
            "parameters:\n"
            "  - name: environment\n"
            "    type: string\n"
            "  - name: workingDirectory\n"
            "    type: string\n"
            "    default: '.'\n"
            "```"
        ),
        "standard_parameters_list": (
            "- `environment` — target environment name (dev/staging/prod)\n"
            "- `workingDirectory` — path to the component/stack\n"
            "- `terraformVersion` — Terraform version to use"
        ),
        "pipeline_conventions": (
            "- Use YAML templates (`template:`) for reusable plan/apply steps\n"
            "- Plan on all branches, apply only on `main` with approval gates\n"
            "- Use Azure DevOps Environments for deployment approvals\n"
            "- Use variable groups for environment-specific secrets\n"
            "- Cache Terraform providers with pipeline caching"
        ),
        "pipeline_conventions_list": (
            "- Templates in `pipelines/templates/`\n"
            "- Plan stage: runs on all branches\n"
            "- Apply stage: runs on `main` with ADO environment approval\n"
            "- Drift detection: scheduled pipeline (nightly)\n"
            "- Use `TerraformTaskV4` or inline `az` + `terraform` commands"
        ),
    },
    "GitLab CI": {
        "pipeline_dir": ".gitlab",
        "pipeline_apply_to": "**/.gitlab-ci.yml",
        "template_reference_pattern": (
            "Store reusable CI includes in `.gitlab/` and reference with\n"
            "`include: - local: .gitlab/terraform.yml`."
        ),
        "standard_parameters": (
            "```yaml\n"
            "variables:\n"
            "  ENVIRONMENT: dev\n"
            "  WORKING_DIR: '.'\n"
            "  TF_VERSION: '1.9.0'\n"
            "```"
        ),
        "standard_parameters_list": (
            "- `ENVIRONMENT` — target environment (dev/staging/prod)\n"
            "- `WORKING_DIR` — path to the component/stack\n"
            "- `TF_VERSION` — Terraform version to use"
        ),
        "pipeline_conventions": (
            "- Use `include:` for reusable pipeline templates\n"
            "- Plan stage on all branches, apply only on protected branches\n"
            "- Use GitLab environments for deployment tracking and approvals\n"
            "- Store secrets in GitLab CI/CD Variables (masked + protected)\n"
            "- Use GitLab's Terraform state HTTP backend"
        ),
        "pipeline_conventions_list": (
            "- Templates in `.gitlab/`\n"
            "- Plan: runs on all branches and merge requests\n"
            "- Apply: manual job on protected branches only\n"
            "- Drift detection: scheduled pipeline\n"
            "- Use `hashicorp/terraform` Docker image"
        ),
    },
    "Atlantis": {
        "pipeline_dir": ".",
        "pipeline_apply_to": "**/atlantis.yaml",
        "template_reference_pattern": (
            "Configure project workflows in `atlantis.yaml` at the repository root."
        ),
        "standard_parameters": (
            "```yaml\n"
            "workflows:\n"
            "  default:\n"
            "    plan:\n"
            "      steps: [init, plan]\n"
            "    apply:\n"
            "      steps: [apply]\n"
            "```"
        ),
        "standard_parameters_list": (
            "- `dir` — path to the Terraform project root\n"
            "- `workspace` — Terraform workspace name\n"
            "- `autoplan` — whether to auto-plan on file change"
        ),
        "pipeline_conventions": (
            "- Define projects in `atlantis.yaml` with `dir` and `workspace`\n"
            "- Apply triggered by PR comment `atlantis apply`\n"
            "- Use Atlantis locks to prevent concurrent applies\n"
            "- Store credentials in server-side environment variables\n"
            "- Enable `--require-approval` for production"
        ),
        "pipeline_conventions_list": (
            "- Projects defined in `atlantis.yaml`\n"
            "- Plan: automatic on PR open/push\n"
            "- Apply: PR comment `atlantis apply -p <project>`\n"
            "- Use `pre_workflow_hooks` for additional validation\n"
            "- Enable `atlantis lock` for change isolation"
        ),
    },
}

AUTH_DEFAULTS: dict[str, dict[str, dict]] = {
    "Azure": {
        "GitHub Actions": {
            "auth_pattern": (
                "```yaml\n"
                "- uses: azure/login@v2\n"
                "  with:\n"
                "    client-id: ${{ secrets.AZURE_CLIENT_ID }}\n"
                "    tenant-id: ${{ secrets.AZURE_TENANT_ID }}\n"
                "    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}\n"
                "```\n"
                "Uses OIDC (federated credentials) — no secret rotation needed."
            ),
            "auth_requirements": (
                "- Configure federated credentials on the Azure App Registration\n"
                "- Set GitHub Actions secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`\n"
                "- Grant the service principal the required RBAC roles on target subscriptions\n"
                "- Use `azure/login@v2` with OIDC — no client secret"
            ),
        },
        "Azure DevOps": {
            "auth_pattern": (
                "Use an Azure service connection with Managed Identity or service principal.\n"
                "Reference in pipelines with `azureSubscription: '<service-connection-name>'`."
            ),
            "auth_requirements": (
                "- Create an Azure DevOps service connection (Workload Identity Federation preferred)\n"
                "- Grant the service principal required RBAC roles\n"
                "- Reference with `azureSubscription` in pipeline tasks\n"
                "- No client secrets — uses federated identity"
            ),
        },
        "GitLab CI": {
            "auth_pattern": (
                "```yaml\n"
                "variables:\n"
                "  ARM_USE_OIDC: true\n"
                "  ARM_TENANT_ID: $AZURE_TENANT_ID\n"
                "  ARM_CLIENT_ID: $AZURE_CLIENT_ID\n"
                "  ARM_SUBSCRIPTION_ID: $AZURE_SUBSCRIPTION_ID\n"
                "```"
            ),
            "auth_requirements": (
                "- Configure OIDC federation between GitLab and Azure AD\n"
                "- Store `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_SUBSCRIPTION_ID` as CI/CD variables\n"
                "- Set `ARM_USE_OIDC=true` and `ARM_USE_AZUREAD=true` for Azure provider"
            ),
        },
        "Atlantis": {
            "auth_pattern": (
                "Set environment variables on the Atlantis server:\n"
                "`ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`\n"
                "Prefer Managed Identity if Atlantis runs on an Azure VM/AKS."
            ),
            "auth_requirements": (
                "- Run Atlantis on Azure infrastructure to use Managed Identity\n"
                "- Or configure service principal environment variables on the Atlantis server\n"
                "- Grant the identity required RBAC roles"
            ),
        },
    },
    "AWS": {
        "GitHub Actions": {
            "auth_pattern": (
                "```yaml\n"
                "- uses: aws-actions/configure-aws-credentials@v4\n"
                "  with:\n"
                "    role-to-assume: ${{ secrets.AWS_ROLE_ARN }}\n"
                "    aws-region: ${{ vars.AWS_REGION }}\n"
                "```\n"
                "Uses OIDC with IAM roles — no access keys needed."
            ),
            "auth_requirements": (
                "- Create an IAM OIDC identity provider for GitHub Actions\n"
                "- Create an IAM role with a trust policy for the GitHub repo\n"
                "- Set `AWS_ROLE_ARN` as a GitHub Actions secret\n"
                "- No long-lived access keys"
            ),
        },
        "GitLab CI": {
            "auth_pattern": (
                "```yaml\n"
                "variables:\n"
                "  AWS_ROLE_ARN: $AWS_ROLE_ARN\n"
                "  AWS_WEB_IDENTITY_TOKEN_FILE: /tmp/web-identity-token\n"
                "```"
            ),
            "auth_requirements": (
                "- Configure IAM OIDC provider for GitLab\n"
                "- Create IAM role with trust policy for GitLab CI\n"
                "- Use `id_tokens` in GitLab CI YAML to get OIDC token"
            ),
        },
        "Azure DevOps": {
            "auth_pattern": (
                "Set AWS credentials as pipeline library variable groups:\n"
                "`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (use IAM roles if on EC2/ECS)."
            ),
            "auth_requirements": (
                "- Create an IAM user with least-privilege policies (or use OIDC if supported)\n"
                "- Store credentials in Azure DevOps variable groups (secrets)\n"
                "- Rotate credentials regularly"
            ),
        },
        "Atlantis": {
            "auth_pattern": (
                "Run Atlantis on EC2/ECS with an attached IAM instance role.\n"
                "No static credentials needed when using instance metadata."
            ),
            "auth_requirements": (
                "- Attach an IAM role to the Atlantis EC2/ECS instance\n"
                "- Grant the role required policies on target accounts\n"
                "- Use AWS STS AssumeRole for cross-account deployments"
            ),
        },
    },
    "GCP": {
        "GitHub Actions": {
            "auth_pattern": (
                "```yaml\n"
                "- uses: google-github-actions/auth@v2\n"
                "  with:\n"
                "    workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}\n"
                "    service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}\n"
                "```\n"
                "Uses Workload Identity Federation — no service account keys."
            ),
            "auth_requirements": (
                "- Create a Workload Identity Pool and Provider for GitHub Actions\n"
                "- Create a service account and bind it to the pool\n"
                "- Set `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` secrets\n"
                "- No service account JSON keys"
            ),
        },
        "GitLab CI": {
            "auth_pattern": (
                "```yaml\n"
                "variables:\n"
                "  GOOGLE_CREDENTIALS: $GCP_SERVICE_ACCOUNT_KEY\n"
                "```\n"
                "Prefer Workload Identity Federation via OIDC over service account keys."
            ),
            "auth_requirements": (
                "- Configure GCP Workload Identity Federation for GitLab\n"
                "- Or store service account key as a masked CI/CD variable\n"
                "- Grant the service account required IAM roles"
            ),
        },
        "Azure DevOps": {
            "auth_pattern": (
                "Store `GOOGLE_CREDENTIALS` (service account JSON) as a\n"
                "secret pipeline variable or use Workload Identity Federation."
            ),
            "auth_requirements": (
                "- Store service account credentials as Azure DevOps secret variable\n"
                "- Grant the service account required IAM roles on target projects\n"
                "- Prefer Workload Identity Federation if ADO supports OIDC"
            ),
        },
        "Atlantis": {
            "auth_pattern": (
                "Run Atlantis on GCE with a service account attached, or set\n"
                "`GOOGLE_CREDENTIALS` environment variable on the Atlantis server."
            ),
            "auth_requirements": (
                "- Attach a service account to the Atlantis GCE instance\n"
                "- Grant the service account required project IAM roles\n"
                "- Use Application Default Credentials (ADC)"
            ),
        },
    },
}
