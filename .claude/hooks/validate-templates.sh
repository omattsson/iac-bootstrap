#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): after a change under references/, rebuild the
# bundled copy and run the template validator, the same first steps CI runs.
# Exits 2 on failure so the output is fed back to Claude.
set -uo pipefail

file=$(jq -r '.tool_input.file_path // empty')
case "$file" in
  */references/*) ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

py=python3
[[ -x .venv/bin/python ]] && py=.venv/bin/python
if ! "$py" -c 'import yaml' 2>/dev/null; then
  echo "validate-templates: pyyaml missing, skipped (python3 -m venv .venv && .venv/bin/pip install pyyaml)" >&2
  exit 0
fi

out=$("$py" scripts/build_templates.py 2>&1 && "$py" scripts/validate_templates.py 2>&1) || {
  echo "$out" >&2
  exit 2
}
