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
def test_check_ignores_line_ending_differences(tmp_path):
    """A CRLF committed file is not drift against LF generation (Windows)."""
    import shutil

    build_examples = _load_build_examples()
    real = _EXAMPLES / "generated" / "azure-terragrunt"
    fake_generated = tmp_path / "generated"
    copied = fake_generated / "azure-terragrunt"
    shutil.copytree(real, copied)
    # Rewrite one committed file with CRLF endings.
    target = copied / "CLAUDE.md"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    assert b"\r\n" in target.read_bytes()

    build_examples.GENERATED_DIR = fake_generated
    problems = build_examples.check()
    assert not any("differs CLAUDE.md" in p for p in problems), problems


@requires_source
def test_build_removes_stale_files_and_keeps_the_config(tmp_path):
    """build() is destructive: it must drop stale output, keep the config
    byte-for-byte, prune emptied directories, and write canonical LF."""
    import shutil

    build_examples = _load_build_examples()
    real = _EXAMPLES / "generated" / "azure-terragrunt"
    copied = tmp_path / "azure-terragrunt"
    shutil.copytree(real, copied)
    config = copied / ".bootstrap-iac.yaml"
    config_bytes = config.read_bytes()

    # Plant stale output at the top level and in a nested directory that
    # generation does not produce, and rewrite one real file with CRLF.
    (copied / "stale.md").write_text("old output\n")
    nested = copied / ".github" / "obsolete"
    nested.mkdir()
    (nested / "old.md").write_text("old output\n")
    claude_md = copied / "CLAUDE.md"
    claude_md.write_bytes(claude_md.read_bytes().replace(b"\n", b"\r\n"))

    build_examples.build([copied])

    assert config.read_bytes() == config_bytes
    assert not (copied / "stale.md").exists()
    assert not nested.exists(), "emptied stale directory was not pruned"
    outputs = [p for p in copied.rglob("*") if p.is_file() and p != config]
    assert outputs, "build() produced no output"
    assert claude_md.is_file()
    assert not any(b"\r\n" in p.read_bytes() for p in outputs)
    # The rebuilt tree equals a fresh generation and matches the committed one.
    assert build_examples.check([copied]) == []
    rebuilt = {p.relative_to(copied).as_posix(): p.read_bytes() for p in outputs}
    committed = {
        p.relative_to(real).as_posix(): p.read_bytes()
        for p in real.rglob("*")
        if p.is_file() and p.name != ".bootstrap-iac.yaml"
    }
    assert rebuilt == committed


@requires_source
def test_check_fails_when_no_reproducible_examples_exist(tmp_path):
    """An empty or missing examples/generated/ is a failure, not a pass, so
    deleting the complete example cannot slip past --check."""
    build_examples = _load_build_examples()
    empty = tmp_path / "generated"
    empty.mkdir()
    build_examples.GENERATED_DIR = empty
    assert any("no reproducible examples" in p for p in build_examples.check())
    build_examples.GENERATED_DIR = tmp_path / "does-not-exist"
    assert any("no reproducible examples" in p for p in build_examples.check())


@requires_source
def test_check_flags_a_generated_dir_without_a_config():
    """A directory under examples/generated/ without a config is reported."""
    build_examples = _load_build_examples()
    orphan = _EXAMPLES / "generated" / "_orphan_no_config"
    orphan.mkdir(parents=True)
    (orphan / "CLAUDE.md").write_text("stale output\n")
    try:
        problems = build_examples.check()
        assert any("_orphan_no_config" in p and "missing" in p for p in problems)
    finally:
        import shutil

        shutil.rmtree(orphan)


@requires_source
def test_generation_is_deterministic_and_ignores_environment(tmp_path):
    build_examples = _load_build_examples()

    # A config that omits `org` and `company` — the values a git remote would
    # feed into discovery. If generation used the surrounding workspace, the
    # planted remote below would leak into one output and differ from the other.
    config = tmp_path / ".bootstrap-iac.yaml"
    config.write_text(
        "cloud: azure\norchestration: none\nci_cd: github-actions\ntarget: copilot\n"
    )

    first = tmp_path / "first"
    second = tmp_path / "second"
    second.mkdir()
    git_config = second / ".git" / "config"
    git_config.parent.mkdir()
    git_config.write_text(
        '[remote "origin"]\n\turl = https://github.com/planted-org/repo.git\n'
    )

    build_examples.generate_into(config, first)
    build_examples.generate_into(config, second)

    def snapshot(root):
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git/" not in p.relative_to(root).as_posix()
        }

    snap_first, snap_second = snapshot(first), snapshot(second)
    assert snap_first == snap_second
    # The planted org must not appear anywhere in the output.
    assert not any(b"planted-org" in content for content in snap_second.values())


@requires_source
def test_config_names_match_the_cli():
    """The harness config names stay in step with the CLI's config filenames."""
    build_examples = _load_build_examples()
    build_examples._ensure_import()
    from bootstrap_iac.config import CONFIG_FILENAMES

    assert tuple(build_examples.CONFIG_NAMES) == tuple(CONFIG_FILENAMES)


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
def test_generated_skill_names_match_their_directories():
    """A skill's frontmatter `name` must equal its directory (for discovery)."""
    import re

    build_examples = _load_build_examples()
    for example in build_examples.reproducible_examples():
        for skill in example.rglob(".github/skills/*/SKILL.md"):
            directory = skill.parent.name
            first = skill.read_text(encoding="utf-8").splitlines()
            name = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in first
                    if re.match(r"^name:\s*", line)
                ),
                None,
            )
            assert name == directory, f"{skill}: name {name!r} != dir {directory!r}"


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
