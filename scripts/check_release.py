#!/usr/bin/env python3
"""Verify a release is consistent: project version, changelog, and git tag.

Run before or during a tagged release so a tag can never ship a version that the
changelog does not document or that the package metadata does not match.

Checks:
  1. CHANGELOG.md has a released section for the project version
     (a ``## [<version>] - <date>`` heading — not the ``[Unreleased]`` section).
  2. When ``--tag`` is given, it equals ``v<project version>``.

Usage:
    python scripts/check_release.py
    python scripts/check_release.py --tag v0.1.0
    python scripts/check_release.py --pyproject cli/pyproject.toml --changelog CHANGELOG.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def pyproject_version(pyproject: Path) -> str:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - exercised on 3.9/3.10 in CI
        import tomli as tomllib  # type: ignore[no-redef]
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def changelog_has_release(changelog_text: str, version: str) -> bool:
    """Return True when the changelog has a released section for *version*.

    Matches a dated heading like ``## [1.2.3] - 2026-09-24``. The date is
    required, so a bare ``## [1.2.3]`` placeholder does not count, and neither
    does the ``[Unreleased]`` section: a release must document its own version
    with a release date.
    """
    pattern = re.compile(
        r"^##\s*\[" + re.escape(version) + r"\]\s*-\s*\d{4}-\d{2}-\d{2}",
        re.MULTILINE,
    )
    return bool(pattern.search(changelog_text))


def tag_matches_version(tag: str, version: str) -> bool:
    """Return True when *tag* is exactly ``v<version>``."""
    return tag == f"v{version}"


def check(
    pyproject: Path, changelog: Path, tag: str | None = None
) -> list[str]:
    problems: list[str] = []
    version = pyproject_version(pyproject)
    if not changelog_has_release(changelog.read_text(encoding="utf-8"), version):
        problems.append(
            f"CHANGELOG.md has no released section for version {version} "
            f"(expected a '## [{version}] - <date>' heading)"
        )
    if tag is not None and not tag_matches_version(tag, version):
        problems.append(
            f"git tag {tag} does not match project version {version} "
            f"(expected tag v{version})"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=REPO_ROOT / "cli" / "pyproject.toml",
    )
    parser.add_argument(
        "--changelog", type=Path, default=REPO_ROOT / "CHANGELOG.md"
    )
    parser.add_argument(
        "--tag",
        help="Git tag being released (for example v0.1.0); checked against the "
        "project version when given.",
    )
    args = parser.parse_args(argv)

    try:
        problems = check(args.pyproject, args.changelog, args.tag)
    except ImportError as exc:  # tomllib is stdlib on 3.11+; else needs tomli
        print(f"ERROR: cannot parse pyproject.toml ({exc}); on Python < 3.11 "
              "install tomli.")
        return 1
    except (OSError, KeyError, ValueError) as exc:
        print(f"ERROR: could not run release checks: {exc}")
        return 1

    if problems:
        print("Release checks FAILED:")
        for problem in problems:
            print(f"    {problem}")
        return 1

    version = pyproject_version(args.pyproject)
    print(f"OK: release checks pass for version {version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
