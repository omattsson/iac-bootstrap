#!/usr/bin/env python3
"""Generate the bundled CLI templates from the canonical references.

``references/`` is the single source of truth for the ``.tmpl`` templates.
The CLI package ships a copy under ``cli/bootstrap_iac/templates/`` so the
installed wheel is self-contained. That copy is generated, not edited by hand,
and is not tracked in git.

Usage:
    python scripts/build_templates.py           # regenerate the bundled copy
    python scripts/build_templates.py --check    # verify the copy is up to date
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCES = REPO_ROOT / "references"
DEFAULT_DEST = REPO_ROOT / "cli" / "bootstrap_iac" / "templates"


def _tmpl_map(root: Path) -> dict[Path, Path]:
    """Map each ``.tmpl`` file's path (relative to *root*) to its absolute path."""
    return {p.relative_to(root): p for p in root.rglob("*.tmpl")}


def _prune_empty_dirs(root: Path) -> None:
    if not root.is_dir():
        return
    for directory in sorted(root.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def build(
    references: Path = DEFAULT_REFERENCES, dest: Path = DEFAULT_DEST
) -> list[str]:
    """Regenerate *dest* from the ``.tmpl`` files in *references*.

    Returns the sorted list of generated relative paths. Stale generated files
    that no longer exist in *references* are removed.
    """
    references = Path(references)
    dest = Path(dest)
    src = _tmpl_map(references)

    if dest.exists():
        for existing in list(dest.rglob("*.tmpl")):
            if existing.relative_to(dest) not in src:
                existing.unlink()

    for rel, path in src.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)

    _prune_empty_dirs(dest)
    return sorted(str(rel) for rel in src)


def check(
    references: Path = DEFAULT_REFERENCES, dest: Path = DEFAULT_DEST
) -> list[str]:
    """Return a list of problems if *dest* does not match *references* exactly."""
    references = Path(references)
    dest = Path(dest)
    src = _tmpl_map(references)
    generated = _tmpl_map(dest)

    problems: list[str] = []
    for rel in sorted(src.keys() - generated.keys()):
        problems.append(f"missing generated template: {rel}")
    for rel in sorted(generated.keys() - src.keys()):
        problems.append(f"stale generated template (not in references): {rel}")
    for rel in sorted(src.keys() & generated.keys()):
        if src[rel].read_bytes() != generated[rel].read_bytes():
            problems.append(f"content differs from references: {rel}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the bundled copy is up to date instead of regenerating it.",
    )
    args = parser.parse_args(argv)

    if not DEFAULT_REFERENCES.is_dir():
        print(f"ERROR: references directory not found: {DEFAULT_REFERENCES}")
        return 1

    if args.check:
        problems = check()
        if problems:
            print("Bundled templates are out of date. Run: python scripts/build_templates.py")
            for problem in problems:
                print(f"    {problem}")
            return 1
        print("Bundled templates are up to date with references/.")
        return 0

    generated = build()
    print(f"Generated {len(generated)} template(s) into {DEFAULT_DEST}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
