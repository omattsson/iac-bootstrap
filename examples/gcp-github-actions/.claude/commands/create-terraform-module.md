# Create Terraform Module (GCP)

Scaffold a new `terraform-google-{name}` directory following Acme GCP workspace conventions.

## Usage
Provide the module name as the argument: `$ARGUMENTS`

If no name is given, ask for:
- Module name (lowercase, hyphenated, e.g., `storage-bucket`, `cloud-run-service`)
- Primary GCP resource type(s) (e.g., `google_storage_bucket`, `google_cloud_run_v2_service`)
- Optional features: Private Service Connect, CMEK, IAM bindings, lifecycle rules

## Directory Structure

```
terraform-google-{name}/
├── main.tf                    # Provider requirements + data sources
├── {resource}.tf              # Core resource(s)
├── locals.tf                  # Name construction, label merging
├── variables.tf               # Module-specific variables
├── common.variables.tf        # Standard cross-module variables
├── outputs.tf                 # Module outputs
├── versions.tf                # Version constraints
├── README.md                  # Documentation
├── .pre-commit-config.yaml    # Validation hooks
├── .tflint.hcl                # TFLint rules
├── .terraform-docs.yml        # Doc generation
├── examples/
│   └── basic/
│       ├── main.tf
│       └── variables.tf
└── tests/
    └── {resource}.tftest.hcl  # Native terraform tests
```

## File Templates

### versions.tf
```hcl
terraform {
  required_version = ">=1.3"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">=5.0,<6.0"
    }
  }
}
```

### locals.tf
```hcl
locals {
  name_suffix = lower(trimprefix(trimsuffix(
    replace(var.suffix, "/[^0-9a-z-]+/", "-"), "-"), "-"))
  name   = substr(var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}", 0, {max_length})
  labels = merge(var.env_default_labels, var.labels)
}
```

### Resource file
```hcl
resource "google_{resource_type}" "default" {
  name    = local.name
  project = var.project
  labels  = local.labels
}
```

### outputs.tf
```hcl
output "name" {
  value       = google_{resource_type}.default.name
  description = "Name of the resource."
}

output "id" {
  value       = google_{resource_type}.default.id
  description = "The ID of the resource."
}
```

### Test file
```hcl
mock_provider "google" {}

variables {
  prefix             = "test-auto"
  project            = "acme-test-000000"
  region             = "us-central1"
  suffix             = "mytest"
  labels             = {}
  env_default_labels = { managed_by = "terraform" }
}

run "creates_resource_with_correct_name" {
  command = plan
  assert {
    condition     = google_{resource_type}.default.name == "test-auto-{abbr}-mytest"
    error_message = "Name should follow naming convention"
  }
}

run "merges_labels_correctly" {
  command = plan
  variables {
    labels = { extra = "label" }
  }
  assert {
    condition     = google_{resource_type}.default.labels["extra"] == "label"
    error_message = "Custom labels should be merged"
  }
}
```

## Post-Creation

Run these commands after scaffolding:
```bash
cd terraform-google-{name}
terraform fmt -recursive
terraform validate
terraform test
```
