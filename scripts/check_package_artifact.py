#!/usr/bin/env python3
"""Verify a built distribution bundles the complete template package data.

A source checkout hides missing package data: the generator and the tests find
``references/`` and ``cli/bootstrap_iac/templates/`` on disk even when the wheel
would ship neither. This script inspects the *built* wheel instead, so CI fails
when the package-data configuration drops templates that an installed user needs.

The bundle carries a manifest (``bootstrap_iac/templates/_manifest.sha256``,
written by scripts/build_templates.py) that lists every template with its hash.
The check reads that manifest from inside the wheel and confirms every listed
template is present in the wheel with a matching hash, and that no extra template
is shipped unlisted. So if setuptools package-data omits a template, the manifest
lists it but the wheel lacks it and the check fails.

Usage:
    python scripts/check_package_artifact.py --wheel dist/pkg.whl
    python scripts/check_package_artifact.py --dist dist/   # newest wheel
    # Also assert the wheel version equals the project version:
    python scripts/check_package_artifact.py --dist dist/ --pyproject cli/pyproject.toml
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

TEMPLATES_PREFIX = "bootstrap_iac/templates/"
MANIFEST_PATH = TEMPLATES_PREFIX + "_manifest.sha256"


def find_wheel(dist_dir: Path) -> Path:
    """Return the newest ``.whl`` under *dist_dir*, or raise if none exists."""
    wheels = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise FileNotFoundError(f"no wheel (*.whl) found under {dist_dir}")
    return wheels[-1]


def parse_manifest(text: str) -> dict[str, str]:
    """Parse ``<sha256>  <relpath>`` lines into a {relpath: hash} mapping."""
    expected: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, rel = line.partition("  ")
        if rel:
            expected[rel] = digest
    return expected


def verify_wheel_templates(wheel: Path) -> list[str]:
    """Return a list of problems with the wheel's bundled template set.

    The wheel must carry a non-empty manifest, every template the manifest lists
    must be present with a matching hash, and no ``.tmpl`` may be shipped that the
    manifest does not list.
    """
    problems: list[str] = []
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        if MANIFEST_PATH not in names:
            return [
                f"{wheel.name}: bundle manifest {MANIFEST_PATH} is missing from "
                "the wheel — package data was not shipped"
            ]
        expected = parse_manifest(zf.read(MANIFEST_PATH).decode("utf-8"))
        if not expected:
            return [f"{wheel.name}: bundle manifest is empty"]

        present = {
            n[len(TEMPLATES_PREFIX):]
            for n in names
            if n.startswith(TEMPLATES_PREFIX) and n.endswith(".tmpl")
        }
        for rel in sorted(set(expected) - present):
            problems.append(f"{wheel.name}: missing template {rel}")
        for rel in sorted(present - set(expected)):
            problems.append(f"{wheel.name}: template not listed in manifest: {rel}")
        for rel in sorted(set(expected) & present):
            digest = hashlib.sha256(zf.read(TEMPLATES_PREFIX + rel)).hexdigest()
            if digest != expected[rel]:
                problems.append(f"{wheel.name}: template hash mismatch: {rel}")
    return problems


def wheel_version(wheel: Path) -> str:
    """Return the version recorded in the wheel's ``*.dist-info/METADATA``."""
    with zipfile.ZipFile(wheel) as zf:
        meta = next(
            (n for n in zf.namelist() if n.endswith(".dist-info/METADATA")), None
        )
        if meta is None:
            raise FileNotFoundError(f"{wheel.name}: no dist-info METADATA in wheel")
        for line in zf.read(meta).decode("utf-8").splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    raise ValueError(f"{wheel.name}: no Version field in METADATA")


def pyproject_version(pyproject: Path) -> str:
    """Return the ``[project] version`` from a pyproject.toml."""
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - exercised on 3.9/3.10 in CI
        import tomli as tomllib  # type: ignore[no-redef]
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--wheel", type=Path, help="Path to a built wheel.")
    group.add_argument("--dist", type=Path, help="Directory holding built wheels.")
    parser.add_argument(
        "--pyproject",
        type=Path,
        help="If given, assert the wheel version equals this project's version.",
    )
    args = parser.parse_args(argv)

    try:
        wheel = args.wheel if args.wheel else find_wheel(args.dist)
        problems = verify_wheel_templates(wheel)
        version = wheel_version(wheel)
        if args.pyproject:
            expected = pyproject_version(args.pyproject)
            if version != expected:
                problems.append(
                    f"{wheel.name}: wheel version {version} does not match project "
                    f"version {expected}"
                )
    except ImportError as exc:  # tomllib is stdlib on 3.11+; else needs tomli
        print(f"ERROR: cannot parse pyproject.toml ({exc}); on Python < 3.11 "
              "install tomli.")
        return 1
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
        print(f"ERROR: could not inspect the artifact: {exc}")
        return 1

    if problems:
        print("Package artifact check FAILED:")
        for problem in problems:
            print(f"    {problem}")
        return 1

    with zipfile.ZipFile(wheel) as zf:
        count = sum(
            1
            for n in zf.namelist()
            if n.startswith(TEMPLATES_PREFIX) and n.endswith(".tmpl")
        )
    print(f"OK: {wheel.name} (version {version}) bundles {count} template(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
