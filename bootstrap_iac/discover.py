"""Workspace discovery: scan an IaC workspace for existing patterns."""

from __future__ import annotations

from pathlib import Path


def discover_workspace(workspace_dir: Path) -> dict:
    """Scan a workspace directory and return a profile of what was found.

    Returns a dict with keys:
        has_terraform      bool   — .tf files found
        has_terragrunt     bool   — terragrunt.hcl files found
        has_terramate      bool   — .tm.hcl files found
        has_github_actions bool   — .github/workflows/*.yml found
        has_azure_devops   bool   — pipelines/*.yml found
        has_gitlab_ci      bool   — .gitlab-ci.yml found
        has_atlantis       bool   — atlantis.yaml found
        has_copilot        bool   — .github/copilot-instructions.md found
        has_claude         bool   — CLAUDE.md found
        module_prefix      str    — guessed module prefix (e.g. tf-module) or ""
        orchestration_dir  str    — guessed orchestration dir or ""
        pipeline_dir       str    — guessed pipeline dir or ""
    """
    ws = workspace_dir.resolve()
    result = {
        "has_terraform": False,
        "has_terragrunt": False,
        "has_terramate": False,
        "has_github_actions": False,
        "has_azure_devops": False,
        "has_gitlab_ci": False,
        "has_atlantis": False,
        "has_copilot": False,
        "has_claude": False,
        "module_prefix": "",
        "orchestration_dir": "",
        "pipeline_dir": "",
    }

    if not ws.exists():
        return result

    # Scan for Terraform files
    tf_files = list(ws.rglob("*.tf"))
    result["has_terraform"] = len(tf_files) > 0

    # Scan for Terragrunt
    tg_files = list(ws.rglob("terragrunt.hcl"))
    result["has_terragrunt"] = len(tg_files) > 0

    # Scan for Terramate
    tm_files = list(ws.rglob("*.tm.hcl"))
    result["has_terramate"] = len(tm_files) > 0

    # CI/CD detection
    gha_dir = ws / ".github" / "workflows"
    if gha_dir.exists() and list(gha_dir.glob("*.yml")):
        result["has_github_actions"] = True
        result["pipeline_dir"] = ".github/workflows"

    if (ws / ".gitlab-ci.yml").exists():
        result["has_gitlab_ci"] = True
        if not result["pipeline_dir"]:
            result["pipeline_dir"] = ".gitlab"

    if (ws / "atlantis.yaml").exists() or (ws / "atlantis.yml").exists():
        result["has_atlantis"] = True

    # Check for Azure DevOps pipeline dirs
    for candidate in ["pipelines", ".pipelines", "azure-pipelines"]:
        if (ws / candidate).exists():
            result["has_azure_devops"] = True
            if not result["pipeline_dir"]:
                result["pipeline_dir"] = candidate
            break

    # Existing AI customizations
    result["has_copilot"] = (ws / ".github" / "copilot-instructions.md").exists()
    result["has_claude"] = (ws / "CLAUDE.md").exists()

    # Guess module prefix from directory names
    for child in ws.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            name = child.name
            for known_prefix in ("tf-module-", "terraform-", "terraform-aws-", "terraform-azure-"):
                if name.startswith(known_prefix):
                    result["module_prefix"] = known_prefix.rstrip("-")
                    break
            if result["module_prefix"]:
                break

    # Guess orchestration dir
    if result["has_terragrunt"]:
        for candidate in ["infrastructure-config", "config", "terragrunt", "infra"]:
            if (ws / candidate).exists() and list((ws / candidate).rglob("terragrunt.hcl")):
                result["orchestration_dir"] = candidate
                break
    elif result["has_terramate"]:
        for candidate in ["stacks", "infra", "infrastructure"]:
            if (ws / candidate).exists():
                result["orchestration_dir"] = candidate
                break

    return result
