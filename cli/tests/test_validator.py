"""Tests for bootstrap_iac.validator."""

from pathlib import Path

import pytest

from bootstrap_iac.validator import find_unreplaced, validate_file, validate_directory


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
    """Non-existent file should return empty list (not raise)."""
    f = tmp_path / "does_not_exist.md"
    assert validate_file(f) == []


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

    results = validate_directory(tmp_path)
    assert len(results) == 2
    # a.md and sub/c.yml have issues
    paths = {str(p.name) for p in results}
    assert "a.md" in paths
    assert "c.yml" in paths


def test_validate_directory_no_issues(tmp_path):
    (tmp_path / "clean.md").write_text("No placeholders")
    results = validate_directory(tmp_path)
    assert results == {}


def test_validate_directory_empty(tmp_path):
    results = validate_directory(tmp_path)
    assert results == {}


def test_validate_directory_skips_binary(tmp_path):
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01{{NOT_SCANNED}}")
    results = validate_directory(tmp_path)
    assert results == {}
