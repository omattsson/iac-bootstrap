"""Tests for reproducible examples (issue #63).

Examples under examples/generated/ carry a bootstrap config and are regenerated
by the CLI. These tests verify generation is deterministic, the committed
examples are up to date, and the complete example has the full Copilot tree.

Skipped when the source tree (scripts/ and examples/) is not reachable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "build_examples.py"
_EXAMPLES = _REPO_ROOT / "examples"

requires_source = pytest.mark.skipif(
    not (_SCRIPT.exists() and _EXAMPLES.is_dir()),
    reason="source tree (scripts/ and examples/) not reachable",
)


def _load_build_examples():
    spec = importlib.util.spec_from_file_location("build_examples", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@requires_source
def test_reproducible_examples_are_up_to_date():
    build_examples = _load_build_examples()
    examples = build_examples.reproducible_examples()
    assert examples, "expected at least one reproducible example"
    problems = build_examples.check(examples)
    assert problems == [], "stale reproducible examples:\n" + "\n".join(problems)


@requires_source
def test_generation_is_deterministic_and_ignores_environment(tmp_path):
    build_examples = _load_build_examples()
    example = build_examples.reproducible_examples()[0]
    config = build_examples._config_path(example)

    first = tmp_path / "first"
    # Plant a differing git remote under the second output dir. Generation must
    # not pick it up — the committed config is the only source of values.
    second = tmp_path / "second"
    second.mkdir()
    git_config = second / ".git" / "config"
    git_config.parent.mkdir()
    git_config.write_text(
        '[remote "origin"]\n\turl = https://github.com/some-other-org/repo.git\n'
    )

    build_examples.generate_into(config, first)
    build_examples.generate_into(config, second)

    def snapshot(root):
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git/" not in p.relative_to(root).as_posix()
        }

    assert snapshot(first) == snapshot(second)


@requires_source
def test_complete_example_has_full_copilot_and_claude_trees():
    example = _EXAMPLES / "generated" / "azure-terragrunt"
    github = example / ".github"
    assert github.is_dir(), "the complete reproducible example is missing"
    copilot = {p.relative_to(github).as_posix() for p in github.rglob("*") if p.is_file()}
    assert copilot == {
        "copilot-instructions.md",
        "agents/infra-architect.agent.md",
        "agents/terraform-module-builder.agent.md",
        "agents/terraform-test-writer.agent.md",
        "agents/terragrunt-stack-manager.agent.md",
        "instructions/terraform-modules.instructions.md",
        "instructions/terraform-tests.instructions.md",
        "instructions/pipeline-templates.instructions.md",
        "instructions/iac-best-practices.instructions.md",
        "instructions/terragrunt-configs.instructions.md",
        "skills/create-terraform-module/SKILL.md",
        "skills/create-infra-pipeline/SKILL.md",
        "skills/create-terragrunt-stack/SKILL.md",
    }

    claude = {".claude/commands/" + p.name for p in (example / ".claude" / "commands").glob("*.md")}
    assert (example / "CLAUDE.md").is_file()
    assert claude == {
        ".claude/commands/create-terraform-module.md",
        ".claude/commands/create-infra-pipeline.md",
        ".claude/commands/create-terragrunt-stack.md",
    }


@requires_source
def test_reproducible_examples_have_no_placeholders():
    import re

    placeholder = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
    build_examples = _load_build_examples()
    for example in build_examples.reproducible_examples():
        for path in example.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".yml", ".yaml"}:
                text = path.read_text(encoding="utf-8")
                assert not placeholder.search(text), f"{path} has a placeholder"
