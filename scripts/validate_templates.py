#!/usr/bin/env python3
"""Validate template files and examples in the iac-bootstrap repository.

Checks:
  1. .tmpl files: all {{...}} placeholders use uppercase letters and underscores only.
  2. Agent and instruction .tmpl files: YAML frontmatter is present and valid.
  3. Example files: no remaining {{...}} tokens.
  4. Templates referenced in SKILL.md all exist on disk.
"""

import re
import sys
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Valid placeholder: uppercase letters and underscores inside {{ }}
PLACEHOLDER_RE = re.compile(r"\{\{([^}]*)\}\}")
VALID_PLACEHOLDER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Files with expected YAML frontmatter
FRONTMATTER_GLOBS = [
    "references/copilot/agents/*.tmpl",
    "references/copilot/instructions/*.tmpl",
]

SKILL_MD = REPO_ROOT / "SKILL.md"
REFERENCES_DIR = REPO_ROOT / "references"
EXAMPLES_DIR = REPO_ROOT / "examples"


def check_placeholder_syntax() -> list[str]:
    """Check that all {{...}} tokens in .tmpl files are uppercase identifiers."""
    errors: list[str] = []
    tmpl_files = list(REPO_ROOT.rglob("*.tmpl"))
    if not tmpl_files:
        errors.append("ERROR: No .tmpl files found under repository root.")
        return errors

    for path in sorted(tmpl_files):
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")

        # Detect unbalanced or malformed braces (e.g. {{{ or single { before word)
        # Check for triple braces
        if "{{{" in text or "}}}" in text:
            errors.append(f"{rel}: contains triple braces '{{{{{{' or '}}}}}}'")

        for match in PLACEHOLDER_RE.finditer(text):
            inner = match.group(1)
            if not VALID_PLACEHOLDER_RE.match(inner):
                line_no = text[: match.start()].count("\n") + 1
                errors.append(
                    f"{rel}:{line_no}: invalid placeholder '{{{{{inner}}}}}'"
                    f" (must be uppercase letters, digits, underscores starting with a letter)"
                )

    return errors


def _extract_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (frontmatter_str, rest) or (None, text) if no frontmatter."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fm = text[3:end].strip()
    rest = text[end + 4 :]
    return fm, rest


def check_yaml_frontmatter() -> list[str]:
    """Validate YAML frontmatter in agent and instruction template files."""
    errors: list[str] = []
    files: list[Path] = []
    for glob in FRONTMATTER_GLOBS:
        files.extend(REPO_ROOT.glob(glob))

    if not files:
        errors.append("ERROR: No agent/instruction template files found for frontmatter check.")
        return errors

    for path in sorted(files):
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")

        fm_str, _ = _extract_frontmatter(text)
        if fm_str is None:
            errors.append(f"{rel}: missing YAML frontmatter (expected '---' block at top of file)")
            continue

        # Replace placeholders with dummy values before parsing YAML so that
        # e.g. `applyTo: "{{MODULE_PREFIX}}-*/**/*.tf"` parses cleanly.
        sanitized = PLACEHOLDER_RE.sub("PLACEHOLDER", fm_str)
        try:
            parsed = yaml.safe_load(sanitized)
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: invalid YAML frontmatter: {exc}")
            continue

        if not isinstance(parsed, dict):
            errors.append(f"{rel}: YAML frontmatter must be a mapping, got {type(parsed).__name__}")
            continue

        if "description" not in parsed:
            errors.append(f"{rel}: YAML frontmatter missing required 'description' field")

    return errors


def check_examples_no_placeholders() -> list[str]:
    """Ensure no {{...}} tokens remain in generated example files."""
    errors: list[str] = []
    example_files = list(EXAMPLES_DIR.rglob("*.md"))
    if not example_files:
        errors.append("ERROR: No .md files found under examples/ directory.")
        return errors

    for path in sorted(example_files):
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")
        matches = list(PLACEHOLDER_RE.finditer(text))
        if matches:
            for m in matches:
                line_no = text[: m.start()].count("\n") + 1
                errors.append(
                    f"{rel}:{line_no}: example file contains unreplaced placeholder '{m.group(0)}'"
                )

    return errors


def check_skill_md_template_references() -> list[str]:
    """Verify every template path mentioned in SKILL.md actually exists."""
    errors: list[str] = []
    skill_text = SKILL_MD.read_text(encoding="utf-8")

    # Extract backtick-quoted paths that end in .tmpl
    # These appear as `copilot/agents/infra-architect.agent.md.tmpl` in SKILL.md
    tmpl_refs = re.findall(r"`([^`]+\.tmpl)`", skill_text)

    if not tmpl_refs:
        errors.append("WARNING: No .tmpl references found in SKILL.md — check the regex.")
        return errors

    seen: set[str] = set()
    for ref in tmpl_refs:
        if ref in seen:
            continue
        seen.add(ref)
        full_path = REFERENCES_DIR / ref
        if not full_path.exists():
            errors.append(
                f"SKILL.md references '{ref}' but file does not exist at references/{ref}"
            )

    return errors


def main() -> int:
    all_errors: list[tuple[str, list[str]]] = []

    checks = [
        ("Placeholder syntax in .tmpl files", check_placeholder_syntax),
        ("YAML frontmatter in agent/instruction templates", check_yaml_frontmatter),
        ("No remaining placeholders in example files", check_examples_no_placeholders),
        ("Template files referenced in SKILL.md exist", check_skill_md_template_references),
    ]

    for label, fn in checks:
        errs = fn()
        all_errors.append((label, errs))

    exit_code = 0
    for label, errs in all_errors:
        if errs:
            print(f"\n❌  {label}")
            for e in errs:
                print(f"    {e}")
            exit_code = 1
        else:
            print(f"✅  {label}")

    if exit_code != 0:
        print("\nValidation failed. Please fix the errors above.")
    else:
        print("\nAll checks passed.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
