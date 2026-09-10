"""In-tree PEP 517 build backend for bootstrap-iac.

``references/`` at the repository root is the single source of truth for the
templates. This backend regenerates ``bootstrap_iac/templates/`` from it before
building, so a package built from the source tree always bundles the current
templates.

Under build isolation ``references/`` is not part of the copied build context,
so the step is skipped and the ``templates/`` already present in the tree is
used. A generation failure while ``references/`` is present propagates and
fails the build, and the build also fails when no templates are available — the
backend never silently ships a partial or empty template set.

``setuptools`` is imported lazily inside the hooks, so the template helpers can
be imported (and tested) in an environment without setuptools.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # the cli/ project directory


def _ensure_templates(references: Path, dest: Path, scripts: Path) -> None:
    """Regenerate *dest* from *references* when it is reachable, then verify.

    When *references* is a directory, the templates are regenerated from it; a
    failure there (a bug in the generator, a permissions problem) propagates and
    fails the build. When *references* is not reachable (an isolated build), the
    templates already present in *dest* are used. Either way, the build fails if
    no templates end up available, so an empty or partial set is never shipped.
    """
    references = Path(references)
    dest = Path(dest)

    if references.is_dir():
        sys.path.insert(0, str(scripts))
        try:
            import build_templates

            build_templates.build(references, dest)
        finally:
            if sys.path and sys.path[0] == str(scripts):
                sys.path.pop(0)

    if not (dest.is_dir() and any(dest.rglob("*.tmpl"))):
        raise RuntimeError(
            "No bundled templates found under bootstrap_iac/templates/ and "
            "references/ is not reachable from the build. Run "
            "`python scripts/build_templates.py` before building the package."
        )


def _regenerate_templates() -> None:
    _ensure_templates(
        _HERE.parent / "references",
        _HERE / "bootstrap_iac" / "templates",
        _HERE.parent / "scripts",
    )


def _backend():
    from setuptools import build_meta

    return build_meta


# ---- PEP 517 hooks (setuptools is imported only when a build actually runs) ---


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _regenerate_templates()
    return _backend().build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    _regenerate_templates()
    return _backend().build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    _regenerate_templates()
    return _backend().build_editable(
        wheel_directory, config_settings, metadata_directory
    )


def get_requires_for_build_wheel(config_settings=None):
    return _backend().get_requires_for_build_wheel(config_settings)


def get_requires_for_build_sdist(config_settings=None):
    return _backend().get_requires_for_build_sdist(config_settings)


def get_requires_for_build_editable(config_settings=None):
    return _backend().get_requires_for_build_editable(config_settings)


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    return _backend().prepare_metadata_for_build_wheel(
        metadata_directory, config_settings
    )


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    return _backend().prepare_metadata_for_build_editable(
        metadata_directory, config_settings
    )
