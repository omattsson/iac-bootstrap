#!/usr/bin/env python3
"""Regenerate the reproducible examples from their committed configs.

An example directory that contains a ``.bootstrap-iac.yaml`` (or ``.yml``) is
reproducible: the CLI regenerates its output from that config, so it stays in
sync with the templates and the generator. These live under
``examples/generated/``. The other ``examples/*`` directories are illustrative
hand-authored SKILL output and are not regenerated here.

Usage:
    python scripts/build_examples.py            # regenerate reproducible examples
    python scripts/build_examples.py --check     # verify they are up to date
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
# Reproducible examples live directly under examples/generated/.
GENERATED_DIR = EXAMPLES_DIR / "generated"
CONFIG_NAMES = (".bootstrap-iac.yaml", ".bootstrap-iac.yml")


def _ensure_import() -> None:
    # Prefer the checkout's package over any installed release, so regeneration
    # always uses the current generator and templates.
    cli = str(REPO_ROOT / "cli")
    if cli not in sys.path:
        sys.path.insert(0, cli)


def reproducible_examples() -> list[Path]:
    """Return each examples/generated/ subdirectory that carries a config."""
    if not GENERATED_DIR.is_dir():
        return []
    found: list[Path] = []
    for entry in sorted(GENERATED_DIR.iterdir()):
        if entry.is_dir() and any((entry / n).is_file() for n in CONFIG_NAMES):
            found.append(entry)
    return found


def _config_path(example: Path) -> Path:
    for name in CONFIG_NAMES:
        candidate = example / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"no bootstrap config in {example}")


def generate_into(config_path: Path, out_dir: Path) -> None:
    """Generate an example's output from *config_path* into an empty *out_dir*.

    Generation uses an empty discovery result, so the committed config is the
    only source of values. This keeps the output independent of the environment
    (for example the surrounding git repository), which is what makes the
    example reproducible.
    """
    _ensure_import()
    from bootstrap_iac.config import load_config
    from bootstrap_iac.discovery import DiscoveryResult
    from bootstrap_iac.generator import generate_files
    from bootstrap_iac.interview import build_context, run_interview

    overrides = load_config(config_path)
    discovery = DiscoveryResult(workspace_path=out_dir)
    answers = run_interview(discovery, non_interactive=True, overrides=overrides)
    context = build_context(answers)
    generate_files(
        context,
        out_dir,
        target=answers.get("TARGET", "both"),
        skip_existing=False,
        # Always render from the canonical references/, never a bundled copy
        # that could be stale, so regeneration reflects the source of truth.
        templates_dir=REPO_ROOT / "references",
    )


def _files(root: Path, exclude: set[str]) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file() and p.relative_to(root).as_posix() not in exclude
    }


def build(examples: list[Path] | None = None) -> None:
    """Regenerate each reproducible example in place, keeping its config."""
    for example in examples if examples is not None else reproducible_examples():
        config = _config_path(example)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            generate_into(config, tmp_dir)
            # Remove old generated files (keep any config), then prune empties.
            # A reproducible example directory holds only its config and
            # generated output; any other file would be removed here.
            keep = set(CONFIG_NAMES)
            for path in sorted(example.rglob("*"), reverse=True):
                rel = path.relative_to(example).as_posix()
                if path.is_file() and rel not in keep:
                    path.unlink()
                elif path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
            for rel, src in _files(tmp_dir, set()).items():
                dst = example / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)


def check(examples: list[Path] | None = None) -> list[str]:
    """Return a list of drift problems for the reproducible examples."""
    problems: list[str] = []
    exclude = set(CONFIG_NAMES)
    for example in examples if examples is not None else reproducible_examples():
        config = _config_path(example)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            generate_into(config, tmp_dir)
            generated = _files(tmp_dir, set())
            committed = _files(example, exclude)
            name = example.relative_to(EXAMPLES_DIR).as_posix()
            for rel in sorted(generated.keys() - committed.keys()):
                problems.append(f"{name}: missing {rel}")
            for rel in sorted(committed.keys() - generated.keys()):
                problems.append(f"{name}: unexpected {rel}")
            for rel in sorted(generated.keys() & committed.keys()):
                if generated[rel].read_bytes() != committed[rel].read_bytes():
                    problems.append(f"{name}: differs {rel}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the reproducible examples are up to date instead of writing.",
    )
    args = parser.parse_args(argv)

    examples = reproducible_examples()
    if not examples:
        print("No reproducible examples found under examples/.")
        return 0

    try:
        if args.check:
            problems = check(examples)
            if problems:
                print(
                    "Reproducible examples are stale. Run: "
                    "python scripts/build_examples.py"
                )
                for problem in problems:
                    print(f"    {problem}")
                return 1
            print(f"{len(examples)} reproducible example(s) up to date.")
            return 0

        build(examples)
        print(f"Regenerated {len(examples)} reproducible example(s).")
        return 0
    except (ValueError, OSError, RuntimeError, yaml.YAMLError) as exc:
        # RuntimeError covers generator.GenerationError (missing template or an
        # unresolved placeholder) and yaml.YAMLError a malformed config, so an
        # invalid config or a broken template prints a clean message instead of
        # a traceback.
        print(f"ERROR: could not process a reproducible example: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
