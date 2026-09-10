"""Tests for template packaging (issue #59).

references/ is the single source of truth. cli/bootstrap_iac/templates/ is a
generated copy produced by scripts/build_templates.py and bundled into the
installed package. These tests verify the generator is faithful, detects drift,
and that the templates the installed package uses match the source.

The tests are skipped when the source tree (references/ and scripts/) is not
reachable, for example in a pure installed environment without the repository.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REFERENCES = _REPO_ROOT / "references"
_BUILD_SCRIPT = _REPO_ROOT / "scripts" / "build_templates.py"
_CLI_DIR = _REPO_ROOT / "cli"


def _load_build_templates():
    if not _BUILD_SCRIPT.exists():
        return None
    spec = importlib.util.spec_from_file_location("build_templates", _BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tmpl_set(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*.tmpl")}


requires_source = pytest.mark.skipif(
    not (_REFERENCES.is_dir() and _BUILD_SCRIPT.exists()),
    reason="source tree (references/ and scripts/) not reachable",
)


@requires_source
def test_generator_reproduces_every_reference_template(tmp_path):
    build_templates = _load_build_templates()
    assert build_templates is not None

    build_templates.build(_REFERENCES, tmp_path)

    assert _tmpl_set(tmp_path) == _tmpl_set(_REFERENCES)
    assert _tmpl_set(tmp_path), "expected at least one template"
    # Content matches byte-for-byte.
    for rel in _tmpl_set(_REFERENCES):
        assert (tmp_path / rel).read_bytes() == (_REFERENCES / rel).read_bytes()
    # check() reports no problems for a freshly generated tree.
    assert build_templates.check(_REFERENCES, tmp_path) == []


@requires_source
def test_check_detects_missing_and_stale_and_changed(tmp_path):
    build_templates = _load_build_templates()
    build_templates.build(_REFERENCES, tmp_path)

    # Remove one file -> missing.
    some = next(iter(_tmpl_set(_REFERENCES)))
    (tmp_path / some).unlink()
    # Add an extra file -> stale.
    (tmp_path / "extra.tmpl").write_text("{{X}}")
    # Change another file -> content differs.
    others = [r for r in _tmpl_set(_REFERENCES) if r != some]
    (tmp_path / others[0]).write_text("changed")

    problems = build_templates.check(_REFERENCES, tmp_path)
    joined = "\n".join(problems)
    assert "missing generated template" in joined
    assert "stale generated template" in joined
    assert "content differs" in joined


@requires_source
def test_build_removes_stale_generated_files(tmp_path):
    build_templates = _load_build_templates()
    build_templates.build(_REFERENCES, tmp_path)
    stale = tmp_path / "gone" / "old.tmpl"
    stale.parent.mkdir(parents=True)
    stale.write_text("{{OLD}}")

    build_templates.build(_REFERENCES, tmp_path)
    assert not stale.exists()
    assert _tmpl_set(tmp_path) == _tmpl_set(_REFERENCES)


@requires_source
def test_sdist_and_wheel_from_sdist_bundle_templates(tmp_path):
    """A default build (sdist then wheel-from-sdist) bundles the templates.

    This inspects the real artifacts, so it exercises the MANIFEST.in contract
    (the backend ships in the sdist so a wheel can build from it) and the
    references/-unavailable path (the wheel is built from the sdist, which has
    no references/). It catches a build that would ship an empty or stale set.
    """
    pytest.importorskip("build")
    build_templates = _load_build_templates()
    # An isolated build copies only cli/, so the on-disk bundle must exist.
    build_templates.build(_REFERENCES, _CLI_DIR / "bootstrap_iac" / "templates")

    proc = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(tmp_path), str(_CLI_DIR)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    # build is a dev dependency, so a failure here is a real regression.
    assert proc.returncode == 0, proc.stderr

    sdists = list(tmp_path.glob("*.tar.gz"))
    wheels = list(tmp_path.glob("*.whl"))
    assert sdists, "no sdist was produced"
    assert wheels, "no wheel was produced"

    # The sdist must ship the build backend so a wheel can build from it.
    import tarfile

    with tarfile.open(sdists[0]) as tf:
        names = tf.getnames()
    assert any(n.endswith("/_bootstrap_build.py") for n in names), (
        "sdist does not ship the build backend"
    )

    # The wheel (built from the sdist) must bundle exactly the reference set,
    # and must not ship the build backend.
    prefix = "bootstrap_iac/templates/"
    with zipfile.ZipFile(wheels[0]) as zf:
        entries = zf.namelist()
    bundled = {
        name[len(prefix):]
        for name in entries
        if prefix in name and name.endswith(".tmpl")
    }
    assert bundled == _tmpl_set(_REFERENCES)
    assert not any("_bootstrap_build" in name for name in entries)


def test_backend_regenerates_and_guards(tmp_path):
    """The build backend regenerates from references/ and refuses an empty set."""
    backend_path = _CLI_DIR / "_bootstrap_build.py"
    if not backend_path.exists() or not _BUILD_SCRIPT.exists():
        pytest.skip("build backend or generator not reachable")
    spec = importlib.util.spec_from_file_location("_bootstrap_build_test", backend_path)
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)

    scripts_dir = _BUILD_SCRIPT.parent

    # references present, empty dest -> regenerates.
    refs = tmp_path / "refs"
    (refs / "sub").mkdir(parents=True)
    (refs / "a.tmpl").write_text("{{A}}")
    (refs / "sub" / "b.tmpl").write_text("{{B}}")
    dest = tmp_path / "dest"
    backend._ensure_templates(refs, dest, scripts_dir)
    assert {p.relative_to(dest).as_posix() for p in dest.rglob("*.tmpl")} == {
        "a.tmpl",
        "sub/b.tmpl",
    }

    # references absent, dest already populated (with a manifest) -> no-op.
    backend._ensure_templates(tmp_path / "missing", dest, scripts_dir)
    assert (dest / "a.tmpl").exists()

    # references absent, dest empty -> refuses to build.
    with pytest.raises(RuntimeError, match="manifest"):
        backend._ensure_templates(tmp_path / "missing", tmp_path / "empty", scripts_dir)

    # references absent, a template from the manifest is missing -> refuses.
    (dest / "sub" / "b.tmpl").unlink()
    with pytest.raises(RuntimeError, match="incomplete or corrupt"):
        backend._ensure_templates(tmp_path / "missing", dest, scripts_dir)

    # references absent, a template differs from its manifest hash -> refuses.
    backend._ensure_templates(refs, dest, scripts_dir)  # rebuild full bundle
    (dest / "a.tmpl").write_text("tampered")
    with pytest.raises(RuntimeError, match="incomplete or corrupt"):
        backend._ensure_templates(tmp_path / "missing", dest, scripts_dir)


@requires_source
def test_templates_used_by_generator_match_references():
    """The templates the package uses match the canonical source exactly.

    In a source checkout get_templates_dir() resolves to the generated bundle
    (or the references/ fallback); in an installed package it resolves to the
    bundled copy in site-packages. Either way it must match references/.
    """
    from bootstrap_iac.generator import get_templates_dir

    tdir = get_templates_dir()
    assert _tmpl_set(tdir) == _tmpl_set(_REFERENCES)
    for rel in _tmpl_set(_REFERENCES):
        assert (tdir / rel).read_bytes() == (_REFERENCES / rel).read_bytes()
