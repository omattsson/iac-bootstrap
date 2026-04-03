# Create Infrastructure Pipeline

Generate GitLab CI pipeline configuration for infrastructure deployments.

## Usage
Describe the pipeline as the argument: `$ARGUMENTS`

If unclear, ask:
- Single component or full stack?
- Which environment(s)?
- Drift detection needed?
- Destroy pipeline needed?

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan** — runs always, publishes plan artifact
2. **Apply** — manual trigger on protected branches only

## Templates

### Single Component Pipeline
```yaml
# ci/{component}-{environment}.gitlab-ci.yml

include:
  - local: ci/terraform-base.gitlab-ci.yml

variables:
  TF_ROOT: config/{environment}/{site}/{stack}/{component}
  TF_PLAN_ARTIFACT: tfplan-{component}-{environment}
  ENVIRONMENT: {environment}

stages:
  - plan
  - apply

plan:{component}:
  stage: plan
  extends: .terraform:plan
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

apply:{component}:
  stage: apply
  extends: .terraform:apply
  needs: ["plan:{component}"]
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual
  environment:
    name: {environment}
```

### Base Job Templates (`ci/terraform-base.gitlab-ci.yml`)
```yaml
.terraform:plan:
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd "$TF_ROOT"
    - terragrunt init -lock-timeout=20m
    - terragrunt plan -out=tfplan -lock-timeout=20m
  artifacts:
    paths:
      - $TF_ROOT/tfplan
    expire_in: 1 day

.terraform:apply:
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd "$TF_ROOT"
    - terragrunt apply -lock-timeout=20m tfplan
```

### Multi-Stack Pipeline
```yaml
# ci/stack-{environment}.gitlab-ci.yml

variables:
  STACK_ROOT: config/{environment}

stages:
  - plan
  - apply

plan:stack:
  stage: plan
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd "$STACK_ROOT"
    - terragrunt run-all plan -lock-timeout=20m
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

apply:stack:
  stage: apply
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd "$STACK_ROOT"
    - terragrunt run-all apply --terragrunt-non-interactive -lock-timeout=20m
  needs: ["plan:stack"]
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### Drift Detection Pipeline
```yaml
# ci/drift-{environment}.gitlab-ci.yml

stages:
  - drift

drift:{environment}:
  stage: drift
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd config/{environment}
    - terragrunt run-all plan -detailed-exitcode -lock-timeout=20m
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  allow_failure: false
```

Schedule in GitLab: Project → CI/CD → Schedules → `0 6 * * 1-5` on `main`.

### Destroy Pipeline
```yaml
# ci/destroy-{component}-{environment}.gitlab-ci.yml

stages:
  - destroy

destroy:{component}:
  stage: destroy
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd config/{environment}/{site}/{stack}/{component}
    - terragrunt destroy --terragrunt-non-interactive -lock-timeout=20m
  when: manual
  environment:
    name: {environment}-destroy
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

## Authentication
- Workload Identity Federation via GitLab `id_tokens` and `az login --federated-token`
- No client secrets — federated credentials only
- CI/CD variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` set at group/project level

## Conventions
- Split pipelines into `ci/` directory, included from root `.gitlab-ci.yml`
- Use `when: manual` for apply jobs — no auto-deploy
- Lock timeout: `-lock-timeout=20m`
- Provider caching: set `TF_PLUGIN_CACHE_DIR` in job or runner config
