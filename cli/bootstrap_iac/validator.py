"""Validate generated output for unreplaced ``{{PLACEHOLDER}}`` tokens."""

from __future__ import annotations

import errno
import os
import re
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
    ``read_errors`` maps each file that could not be read to the OS error
    reason. The two are kept apart so a permissions problem is never mistaken
    for a clean file.
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
    if not path.exists():
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), str(path)
        )
    if path.suffix.lower() not in _TEXT_EXTENSIONS:
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        # The file vanished between exists() and read (a race). Surface it as a
        # missing file so callers treat both vanish-races identically.
        raise
    except OSError as exc:
        raise ValidationReadError(path, exc.strerror or str(exc)) from exc
    return find_unreplaced(content)


def validate_directory(path: Path) -> DirectoryReport:
    """Recursively scan *path* and return a :class:`DirectoryReport`.

    Only files with recognised text extensions are scanned. Files with no
    unreplaced placeholders are omitted. Files that cannot be read are recorded
    in ``read_errors`` instead of being silently treated as clean.
    """
    placeholders: dict[Path, list[str]] = {}
    read_errors: dict[Path, str] = {}
    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        try:
            unreplaced = validate_file(file_path)
        except ValidationReadError as exc:
            read_errors[file_path] = exc.reason
            continue
        except FileNotFoundError:
            # The entry vanished between rglob() and read (a race); skip it.
            continue
        except OSError as exc:
            # A stat/read problem that is not a plain "missing" (for example a
            # symlink loop or too-long name). Record it rather than aborting the
            # whole scan with a traceback.
            read_errors[file_path] = exc.strerror or str(exc)
            continue
        if unreplaced:
            placeholders[file_path] = unreplaced
    return DirectoryReport(placeholders=placeholders, read_errors=read_errors)
