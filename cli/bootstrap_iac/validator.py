"""Validate generated output for unreplaced ``{{PLACEHOLDER}}`` tokens."""

from __future__ import annotations

import re
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

# File extensions to scan
_TEXT_EXTENSIONS = {
    ".md", ".yml", ".yaml", ".tf", ".hcl", ".json", ".toml", ".txt",
}


def find_unreplaced(content: str) -> list[str]:
    """Return a sorted, de-duplicated list of unreplaced placeholder names."""
    return sorted(set(_PLACEHOLDER_RE.findall(content)))


def validate_file(path: Path) -> list[str]:
    """Return unreplaced placeholders found in *path*.

    Returns an empty list if the file is binary or cannot be read.
    """
    if path.suffix.lower() not in _TEXT_EXTENSIONS:
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return find_unreplaced(content)


def validate_directory(path: Path) -> dict[Path, list[str]]:
    """Recursively scan *path* and return a mapping of file → unreplaced placeholders.

    Only files with recognised text extensions are scanned. Files with no
    unreplaced placeholders are omitted from the result.
    """
    results: dict[Path, list[str]] = {}
    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        unreplaced = validate_file(file_path)
        if unreplaced:
            results[file_path] = unreplaced
    return results
