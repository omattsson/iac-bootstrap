"""Tests for the packaging and release checks (issue #64).

These cover scripts/check_package_artifact.py and scripts/check_release.py by
constructing minimal fixtures, so they run without building a real wheel.

Skipped when the source tree (scripts/) is not reachable.
"""

from __future__ import annotations

import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_SCRIPT = _REPO_ROOT / "scripts" / "check_package_artifact.py"
_RELEASE_SCRIPT = _REPO_ROOT / "scripts" / "check_release.py"

requires_source = pytest.mark.skipif(
    not (_ARTIFACT_SCRIPT.exists() and _RELEASE_SCRIPT.exists()),
    reason="source tree (scripts/) not reachable",
)


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_wheel(
    path: Path,
    templates: dict[str, bytes],
    *,
    manifest_entries: dict[str, str] | None = None,
    version: str = "1.0.0",
    include_manifest: bool = True,
) -> Path:
    """Write a minimal wheel-shaped zip.

    *templates* maps a path relative to bootstrap_iac/templates/ to its bytes.
    *manifest_entries* overrides what the manifest lists (defaults to the real
    hashes of *templates*), so a caller can plant a missing or mismatched entry.
    """
    prefix = "bootstrap_iac/templates/"
    if manifest_entries is None:
        manifest_entries = {
            rel: hashlib.sha256(data).hexdigest() for rel, data in templates.items()
        }
    with zipfile.ZipFile(path, "w") as zf:
        for rel, data in templates.items():
            zf.writestr(prefix + rel, data)
        if include_manifest:
            manifest = "\n".join(f"{h}  {rel}" for rel, h in manifest_entries.items())
            zf.writestr(prefix + "_manifest.sha256", manifest + "\n")
        zf.writestr(
            f"bootstrap_iac-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: bootstrap-iac\nVersion: {version}\n",
        )
    return path


# --- check_package_artifact --------------------------------------------------


@requires_source
def test_artifact_accepts_a_complete_bundle(tmp_path):
    m = _load(_ARTIFACT_SCRIPT)
    wheel = _make_wheel(
        tmp_path / "pkg.whl",
        {"copilot/a.tmpl": b"alpha\n", "claude/b.tmpl": b"beta\n"},
    )
    assert m.verify_wheel_templates(wheel) == []
    assert m.wheel_version(wheel) == "1.0.0"


@requires_source
def test_artifact_detects_a_template_missing_from_the_wheel(tmp_path):
    """The core guard: the manifest lists a template the wheel does not ship."""
    m = _load(_ARTIFACT_SCRIPT)
    # Manifest lists two, but only one file is actually in the wheel.
    wheel = _make_wheel(
        tmp_path / "pkg.whl",
        {"copilot/a.tmpl": b"alpha\n"},
        manifest_entries={
            "copilot/a.tmpl": hashlib.sha256(b"alpha\n").hexdigest(),
            "claude/b.tmpl": hashlib.sha256(b"beta\n").hexdigest(),
        },
    )
    problems = m.verify_wheel_templates(wheel)
    assert any("missing template claude/b.tmpl" in p for p in problems)


@requires_source
def test_artifact_detects_a_hash_mismatch(tmp_path):
    m = _load(_ARTIFACT_SCRIPT)
    wheel = _make_wheel(
        tmp_path / "pkg.whl",
        {"copilot/a.tmpl": b"alpha\n"},
        manifest_entries={"copilot/a.tmpl": hashlib.sha256(b"OTHER\n").hexdigest()},
    )
    problems = m.verify_wheel_templates(wheel)
    assert any("hash mismatch" in p for p in problems)


@requires_source
def test_artifact_detects_an_unlisted_template(tmp_path):
    m = _load(_ARTIFACT_SCRIPT)
    wheel = _make_wheel(
        tmp_path / "pkg.whl",
        {"copilot/a.tmpl": b"alpha\n", "extra/c.tmpl": b"gamma\n"},
        manifest_entries={"copilot/a.tmpl": hashlib.sha256(b"alpha\n").hexdigest()},
    )
    problems = m.verify_wheel_templates(wheel)
    assert any("not listed in manifest" in p for p in problems)


@requires_source
def test_artifact_detects_a_missing_manifest(tmp_path):
    m = _load(_ARTIFACT_SCRIPT)
    wheel = _make_wheel(
        tmp_path / "pkg.whl",
        {"copilot/a.tmpl": b"alpha\n"},
        include_manifest=False,
    )
    problems = m.verify_wheel_templates(wheel)
    assert any("manifest" in p and "missing" in p for p in problems)


@requires_source
def test_artifact_main_flags_version_mismatch(tmp_path, capsys):
    m = _load(_ARTIFACT_SCRIPT)
    # A template-complete wheel, so the only possible failure is the version.
    wheel = _make_wheel(
        tmp_path / "pkg.whl", {"copilot/a.tmpl": b"alpha\n"}, version="1.0.0"
    )
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "bootstrap-iac"\nversion = "2.0.0"\n')
    rc = m.main(["--wheel", str(wheel), "--pyproject", str(pyproject)])
    assert rc == 1
    out = capsys.readouterr().out
    # The failure must be the version mismatch, not an incidental problem.
    assert "does not match project version 2.0.0" in out


@requires_source
def test_artifact_main_reports_a_missing_wheel(tmp_path, capsys):
    m = _load(_ARTIFACT_SCRIPT)
    empty = tmp_path / "dist"
    empty.mkdir()
    assert m.main(["--dist", str(empty)]) == 1
    assert "no wheel" in capsys.readouterr().out


@requires_source
def test_artifact_main_accepts_a_good_wheel_by_dist_dir(tmp_path):
    m = _load(_ARTIFACT_SCRIPT)
    dist = tmp_path / "dist"
    dist.mkdir()
    _make_wheel(dist / "pkg.whl", {"copilot/a.tmpl": b"alpha\n"}, version="0.1.0")
    assert m.main(["--dist", str(dist)]) == 0


@requires_source
def test_artifact_main_handles_a_corrupt_wheel(tmp_path, capsys):
    m = _load(_ARTIFACT_SCRIPT)
    bad = tmp_path / "pkg.whl"
    bad.write_bytes(b"not a zip file")
    assert m.main(["--wheel", str(bad)]) == 1
    assert "could not inspect the artifact" in capsys.readouterr().out


@requires_source
def test_artifact_main_accepts_a_good_wheel(tmp_path):
    m = _load(_ARTIFACT_SCRIPT)
    wheel = _make_wheel(
        tmp_path / "pkg.whl", {"copilot/a.tmpl": b"alpha\n"}, version="0.1.0"
    )
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "bootstrap-iac"\nversion = "0.1.0"\n')
    assert m.main(["--wheel", str(wheel), "--pyproject", str(pyproject)]) == 0


# --- check_release -----------------------------------------------------------


def _release_fixture(tmp_path, version: str, changelog: str):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "bootstrap-iac"\nversion = "{version}"\n')
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(changelog)
    return pyproject, cl


@requires_source
def test_release_accepts_a_documented_version_and_matching_tag(tmp_path):
    m = _load(_RELEASE_SCRIPT)
    pyproject, cl = _release_fixture(
        tmp_path, "1.2.3", "# Changelog\n\n## [1.2.3] - 2026-01-01\n\n- Thing\n"
    )
    assert m.check(pyproject, cl, tag="v1.2.3") == []


@requires_source
def test_release_flags_a_missing_changelog_entry(tmp_path):
    m = _load(_RELEASE_SCRIPT)
    pyproject, cl = _release_fixture(
        tmp_path, "1.2.3", "# Changelog\n\n## [Unreleased]\n\n- Thing\n"
    )
    problems = m.check(pyproject, cl)
    assert any("no released section for version 1.2.3" in p for p in problems)


@requires_source
def test_release_flags_a_tag_that_does_not_match_the_version(tmp_path):
    m = _load(_RELEASE_SCRIPT)
    pyproject, cl = _release_fixture(
        tmp_path, "1.2.3", "# Changelog\n\n## [1.2.3] - 2026-01-01\n\n- Thing\n"
    )
    problems = m.check(pyproject, cl, tag="v9.9.9")
    assert any("does not match project version" in p for p in problems)


@requires_source
def test_release_unreleased_section_does_not_satisfy_a_version(tmp_path):
    """A release must document its own version, not rely on [Unreleased]."""
    m = _load(_RELEASE_SCRIPT)
    assert not m.changelog_has_release("## [Unreleased]\n", "0.1.0")
    assert m.changelog_has_release("## [0.1.0] - 2026-09-24\n", "0.1.0")


@requires_source
def test_release_requires_a_dated_changelog_heading(tmp_path):
    """A bare, undated ``## [x.y.z]`` heading does not count as a release."""
    m = _load(_RELEASE_SCRIPT)
    assert not m.changelog_has_release("## [0.1.0]\n\n- Thing\n", "0.1.0")
    assert m.changelog_has_release("## [0.1.0] - 2026-09-24\n", "0.1.0")


@requires_source
def test_release_rejects_impossible_dates_and_trailing_text(tmp_path):
    """The date must be a real calendar date and the heading must end cleanly."""
    m = _load(_RELEASE_SCRIPT)
    assert not m.changelog_has_release("## [0.1.0] - 2026-99-99\n", "0.1.0")
    assert not m.changelog_has_release("## [0.1.0] - 2026-13-01\n", "0.1.0")
    assert not m.changelog_has_release("## [0.1.0] - 2026-09-24 draft\n", "0.1.0")
    # A clean heading and the Keep a Changelog [YANKED] marker are accepted.
    assert m.changelog_has_release("## [0.1.0] - 2026-09-24\n", "0.1.0")
    assert m.changelog_has_release("## [0.1.0] - 2026-09-24 [YANKED]\n", "0.1.0")


@requires_source
def test_release_main_passes_and_fails_via_argv(tmp_path, capsys):
    m = _load(_RELEASE_SCRIPT)
    pyproject, cl = _release_fixture(
        tmp_path, "1.2.3", "# Changelog\n\n## [1.2.3] - 2026-01-01\n\n- Thing\n"
    )
    ok = m.main(
        ["--pyproject", str(pyproject), "--changelog", str(cl), "--tag", "v1.2.3"]
    )
    assert ok == 0
    assert "release checks pass" in capsys.readouterr().out

    bad = m.main(
        ["--pyproject", str(pyproject), "--changelog", str(cl), "--tag", "v9.9.9"]
    )
    assert bad == 1
    assert "does not match project version" in capsys.readouterr().out


# --- the repo's own metadata stays consistent --------------------------------


@requires_source
def test_repo_changelog_documents_the_current_version():
    m = _load(_RELEASE_SCRIPT)
    version = m.pyproject_version(_REPO_ROOT / "cli" / "pyproject.toml")
    changelog = (_REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert m.changelog_has_release(changelog, version), (
        f"CHANGELOG.md must document the current version {version}"
    )


@requires_source
def test_cli_version_matches_the_project_version():
    """The CLI's reported version must match pyproject, so a release tag (which
    check_release ties to pyproject) also matches what `bootstrap-iac --version`
    prints. Guards against the two version sources drifting apart."""
    m = _load(_RELEASE_SCRIPT)
    project_version = m.pyproject_version(_REPO_ROOT / "cli" / "pyproject.toml")
    from bootstrap_iac import __version__

    assert __version__ == project_version, (
        f"bootstrap_iac.__version__ ({__version__}) != pyproject version "
        f"({project_version}); update cli/bootstrap_iac/__init__.py"
    )


@requires_source
def test_repo_classifiers_cover_the_declared_python_floor():
    """Each Python minor from the requires-python floor up is a classifier."""
    art = _load(_ARTIFACT_SCRIPT)
    pyproject = _REPO_ROOT / "cli" / "pyproject.toml"
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    requires = data["project"]["requires-python"]  # e.g. ">=3.9"
    floor_minor = int(requires.split("3.")[1].split(",")[0].strip())
    classifiers = data["project"]["classifiers"]
    versioned = {
        c.rsplit("::", 1)[1].strip()
        for c in classifiers
        if c.startswith("Programming Language :: Python :: 3.")
    }
    assert f"3.{floor_minor}" in versioned, (
        f"missing a classifier for the declared floor 3.{floor_minor}"
    )
    # Ensure check_package_artifact exposes the version reader it advertises.
    assert hasattr(art, "pyproject_version")
