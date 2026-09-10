"""In-tree PEP 517 build backend for bootstrap-iac.

``references/`` at the repository root is the single source of truth for the
templates. This backend regenerates ``bootstrap_iac/templates/`` from it before
building, so a package built from the source tree always bundles the current
templates.

Under build isolation ``references/`` is not part of the copied build context,
so the step is skipped and the ``templates/`` already present in the tree is
used. Regeneration never fails the build.
"""

from __future__ import annotations

import sys
from pathlib import Path

from setuptools import build_meta as _default

_HERE = Path(__file__).resolve().parent  # the cli/ project directory


def _regenerate_templates() -> None:
    references = _HERE.parent / "references"
    dest = _HERE / "bootstrap_iac" / "templates"

    if references.is_dir():
        # Source-tree build: regenerate from the canonical templates. A failure
        # here (a bug in the generator, a permissions problem) must fail the
        # build rather than silently ship a partial or empty template set.
        scripts = _HERE.parent / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import build_templates

            build_templates.build(references, dest)
        finally:
            if sys.path and sys.path[0] == str(scripts):
                sys.path.pop(0)

    # Guard: never build a package with no bundled templates. When references/
    # is not reachable (an isolated build of a fresh checkout), the templates
    # must already be present (run scripts/build_templates.py first).
    if not (dest.is_dir() and any(dest.rglob("*.tmpl"))):
        raise RuntimeError(
            "No bundled templates found under bootstrap_iac/templates/ and "
            "references/ is not reachable from the build. Run "
            "`python scripts/build_templates.py` before building the package."
        )


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _regenerate_templates()
    return _default.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    _regenerate_templates()
    return _default.build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    _regenerate_templates()
    return _default.build_editable(wheel_directory, config_settings, metadata_directory)


# Re-export the remaining PEP 517 hooks unchanged. Optional hooks are only
# defined here when setuptools provides them, so a frontend never sees a hook
# name bound to None.
get_requires_for_build_wheel = _default.get_requires_for_build_wheel
get_requires_for_build_sdist = _default.get_requires_for_build_sdist
prepare_metadata_for_build_wheel = _default.prepare_metadata_for_build_wheel

if hasattr(_default, "get_requires_for_build_editable"):
    get_requires_for_build_editable = _default.get_requires_for_build_editable
if hasattr(_default, "prepare_metadata_for_build_editable"):
    prepare_metadata_for_build_editable = _default.prepare_metadata_for_build_editable
