"""Validate generated output for unreplaced ``{{PLACEHOLDER}}`` tokens."""

from __future__ import annotations

import errno
import os
import re
import stat as stat_module
from dataclasses import dataclass, field
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

# File extensions to scan
_TEXT_EXTENSIONS = {
    ".md", ".yml", ".yaml", ".tf", ".hcl", ".json", ".toml", ".txt",
}


class ValidationReadError(Exception):
    """A supported file exists but could not be read as text.

    Carries the offending ``path`` and the OS error ``reason`` so callers can
    report both without re-deriving them from the message.
    """

    def __init__(self, path: Path, reason: str) -> None:
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"{self.path}: {reason}")


@dataclass(frozen=True)
class DirectoryReport:
    """Outcome of scanning a directory.

    ``placeholders`` maps each file with unreplaced tokens to its findings.
    ``read_errors`` maps each path that could not be read — a file, or a
    directory that could not be scanned — to the OS error reason. The two are
    kept apart so a permissions problem is never mistaken for a clean file.
    """

    placeholders: dict[Path, list[str]] = field(default_factory=dict)
    read_errors: dict[Path, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when no placeholders and no read errors were found."""
        return not self.placeholders and not self.read_errors


def find_unreplaced(content: str) -> list[str]:
    """Return a sorted, de-duplicated list of unreplaced placeholder names."""
    return sorted(set(_PLACEHOLDER_RE.findall(content)))


def validate_file(path: Path) -> list[str]:
    """Return unreplaced placeholders found in *path*.

    Returns an empty list for a clean text file, and also for a file with an
    unsupported (for example binary) extension, which is ignored by design.

    Raises:
        FileNotFoundError: if *path* does not exist. A missing path is treated
            as an error, not a clean result, so a mistyped path cannot look
            like a successful validation.
        ValidationReadError: if *path* exists with a supported extension but
            cannot be read (for example a permissions problem).
    """
    if path.suffix.lower() not in _TEXT_EXTENSIONS:
        # Unsupported (for example binary) extensions are ignored, but a
        # missing path is still an error, so a mistyped path never looks like a
        # clean result. exists() suppresses a few OS errors (for example a
        # symlink loop) and returns False; treating those as missing is
        # acceptable for a file we would not read anyway.
        if not path.exists():
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), str(path)
            )
        return []
    # For a supported extension, read directly and let the OS classify the
    # outcome. This avoids a redundant stat and the race it would open, and it
    # reports symlink loops or traversal errors as read errors rather than
    # misreporting them as missing.
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        # A missing file is not a read error. FileNotFoundError is an OSError
        # subclass, so re-raise it here before the generic handler wraps it.
        raise
    except OSError as exc:
        raise ValidationReadError(path, exc.strerror or str(exc)) from exc
    return find_unreplaced(content)


def validate_directory(path: Path) -> DirectoryReport:
    """Recursively scan *path* and return a :class:`DirectoryReport`.

    Only files with recognised text extensions are scanned. Files with no
    unreplaced placeholders are omitted. Directories that cannot be scanned and
    files that cannot be read are recorded in ``read_errors`` instead of being
    silently treated as clean.
    """
    placeholders: dict[Path, list[str]] = {}
    read_errors: dict[Path, str] = {}

    def _on_walk_error(exc: OSError) -> None:
        # A directory could not be scanned (for example a permissions problem).
        # Record it rather than letting the walk abort with a traceback or, on
        # some Python versions, silently drop the whole subtree. os.walk sets
        # ``filename`` to the offending directory.
        errored = Path(getattr(exc, "filename", None) or path)
        read_errors[errored] = exc.strerror or str(exc)

    files: list[Path] = []
    for dir_path, _dirnames, filenames in os.walk(path, onerror=_on_walk_error):
        base = Path(dir_path)
        files.extend(base / name for name in filenames)

    for file_path in sorted(files):
        # Classify the entry with an explicit stat rather than Path.is_file(),
        # which suppresses most OS errors (for example a symlink loop) and
        # returns False, which would silently drop the entry instead of
        # recording it.
        try:
            st = os.stat(file_path)
        except FileNotFoundError:
            # A dangling symlink or an entry that vanished after the walk; skip.
            continue
        except OSError as exc:
            read_errors[file_path] = exc.strerror or str(exc)
            continue
        if not stat_module.S_ISREG(st.st_mode):
            # Not a regular file (for example a FIFO or socket); nothing to
            # read, and reading some of these would block.
            continue
        try:
            unreplaced = validate_file(file_path)
        except ValidationReadError as exc:
            read_errors[file_path] = exc.reason
            continue
        except FileNotFoundError:
            # The entry vanished between the stat and the read (a race); skip it.
            continue
        except OSError as exc:
            # A read problem that is not a plain "missing". Record it rather
            # than aborting the whole scan with a traceback.
            read_errors[file_path] = exc.strerror or str(exc)
            continue
        if unreplaced:
            placeholders[file_path] = unreplaced
    return DirectoryReport(placeholders=placeholders, read_errors=read_errors)
