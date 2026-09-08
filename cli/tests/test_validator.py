"""Tests for bootstrap_iac.validator."""

import os
import sys
from pathlib import Path

import pytest

from bootstrap_iac.validator import (
    DirectoryReport,
    ValidationReadError,
    find_unreplaced,
    validate_directory,
    validate_file,
)


# ---------------------------------------------------------------------------
# find_unreplaced
# ---------------------------------------------------------------------------


def test_find_unreplaced_simple():
    content = "Hello {{COMPANY_NAME}} and {{CLOUD_PROVIDER}}!"
    result = find_unreplaced(content)
    assert result == ["CLOUD_PROVIDER", "COMPANY_NAME"]


def test_find_unreplaced_no_placeholders():
    content = "No placeholders here."
    assert find_unreplaced(content) == []


def test_find_unreplaced_deduplicates():
    content = "{{X}} and {{X}} again"
    assert find_unreplaced(content) == ["X"]


def test_find_unreplaced_sorted():
    content = "{{ZZZ}} then {{AAA}}"
    assert find_unreplaced(content) == ["AAA", "ZZZ"]


def test_find_unreplaced_lowercase_not_matched():
    """Lowercase is not a placeholder pattern (we use uppercase only)."""
    content = "{{lowercase}} is not a placeholder"
    assert find_unreplaced(content) == []


def test_find_unreplaced_partial_braces_not_matched():
    content = "{SINGLE_BRACE} and {{DOUBLE}}"
    assert find_unreplaced(content) == ["DOUBLE"]


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------


def test_validate_file_with_placeholders(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("Hello {{COMPANY_NAME}} and {{CLOUD_PROVIDER}}!")
    result = validate_file(f)
    assert "COMPANY_NAME" in result
    assert "CLOUD_PROVIDER" in result


def test_validate_file_clean(tmp_path):
    f = tmp_path / "clean.md"
    f.write_text("No placeholders here.")
    assert validate_file(f) == []


def test_validate_file_unsupported_extension(tmp_path):
    f = tmp_path / "binary.exe"
    f.write_bytes(b"\x00\x01\x02")
    assert validate_file(f) == []


def test_validate_file_nonexistent(tmp_path):
    """A missing file is an error, not a clean result."""
    f = tmp_path / "does_not_exist.md"
    with pytest.raises(FileNotFoundError):
        validate_file(f)


def test_validate_file_missing_binary_extension_still_errors(tmp_path):
    """A missing path errors regardless of extension (path typo, not ignore)."""
    f = tmp_path / "does_not_exist.exe"
    with pytest.raises(FileNotFoundError):
        validate_file(f)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX file permissions not enforced for root or on Windows",
)
def test_validate_file_unreadable(tmp_path):
    """An unreadable text file raises ValidationReadError with path detail."""
    f = tmp_path / "locked.md"
    f.write_text("{{COMPANY_NAME}}")
    f.chmod(0o000)
    try:
        with pytest.raises(ValidationReadError) as exc_info:
            validate_file(f)
        assert str(f) in str(exc_info.value)
        assert exc_info.value.path == f
        assert exc_info.value.reason
    finally:
        f.chmod(0o644)


def test_validate_file_yaml(tmp_path):
    f = tmp_path / "pipeline.yml"
    f.write_text("name: {{COMPANY_NAME}}-pipeline\non: push")
    result = validate_file(f)
    assert "COMPANY_NAME" in result


def test_validate_file_hcl(tmp_path):
    f = tmp_path / "config.hcl"
    f.write_text('source = "git::{{MODULE_SOURCE_PATTERN}}"')
    result = validate_file(f)
    assert "MODULE_SOURCE_PATTERN" in result


# ---------------------------------------------------------------------------
# validate_directory
# ---------------------------------------------------------------------------


def test_validate_directory_finds_issues(tmp_path):
    (tmp_path / "a.md").write_text("{{COMPANY_NAME}}")
    (tmp_path / "b.md").write_text("clean")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "c.yml").write_text("{{CLOUD_PROVIDER}}")

    report = validate_directory(tmp_path)
    assert isinstance(report, DirectoryReport)
    assert not report.ok
    assert len(report.placeholders) == 2
    assert report.read_errors == {}
    # a.md and sub/c.yml have issues
    paths = {p.name for p in report.placeholders}
    assert "a.md" in paths
    assert "c.yml" in paths


def test_validate_directory_no_issues(tmp_path):
    (tmp_path / "clean.md").write_text("No placeholders")
    report = validate_directory(tmp_path)
    assert report.ok
    assert report.placeholders == {}
    assert report.read_errors == {}


def test_validate_directory_empty(tmp_path):
    report = validate_directory(tmp_path)
    assert report.ok


def test_validate_directory_skips_binary(tmp_path):
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01{{NOT_SCANNED}}")
    report = validate_directory(tmp_path)
    assert report.ok


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX file permissions not enforced for root or on Windows",
)
def test_validate_directory_reports_read_errors_separately(tmp_path):
    """An unreadable file is a read error, kept apart from placeholder findings."""
    (tmp_path / "dirty.md").write_text("{{COMPANY_NAME}}")
    locked = tmp_path / "locked.md"
    locked.write_text("{{CLOUD_PROVIDER}}")
    locked.chmod(0o000)
    try:
        report = validate_directory(tmp_path)
        assert not report.ok
        assert set(p.name for p in report.placeholders) == {"dirty.md"}
        assert set(p.name for p in report.read_errors) == {"locked.md"}
        assert report.read_errors[locked]
    finally:
        locked.chmod(0o644)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="POSIX file permissions not enforced for root or on Windows",
)
def test_validate_directory_reports_unscannable_subdir(tmp_path):
    """An unreadable subdirectory is recorded, not silently dropped as clean."""
    (tmp_path / "top.md").write_text("{{COMPANY_NAME}}")
    locked_dir = tmp_path / "locked_dir"
    locked_dir.mkdir()
    (locked_dir / "deep.md").write_text("{{CLOUD_PROVIDER}}")
    locked_dir.chmod(0o000)
    try:
        report = validate_directory(tmp_path)
        assert not report.ok
        assert set(p.name for p in report.placeholders) == {"top.md"}
        # The subtree cannot be scanned, so it is reported as a read error
        # rather than passing as clean.
        assert any(p.name == "locked_dir" for p in report.read_errors)
    finally:
        locked_dir.chmod(0o755)


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlink creation needs privileges on Windows"
)
def test_validate_directory_reports_symlink_loop(tmp_path):
    """A symlink loop is recorded, not silently dropped by is_file()."""
    (tmp_path / "ok.md").write_text("{{COMPANY_NAME}}")
    loop = tmp_path / "loop.md"
    try:
        loop.symlink_to("loop.md")  # points at itself -> ELOOP on resolution
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported here")
    report = validate_directory(tmp_path)
    assert not report.ok
    assert set(p.name for p in report.placeholders) == {"ok.md"}
    assert any(p.name == "loop.md" for p in report.read_errors)
