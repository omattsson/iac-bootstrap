#!/usr/bin/env bash
# validate.sh — scan generated output for unreplaced {{PLACEHOLDER}} tokens
#
# Usage:
#   scripts/validate.sh [target-dir]
#
# If target-dir is provided, it is used as the root to scan instead of the
# current working directory. This lets you validate a bootstrapped workspace
# without changing into it first.
#
# Scans: .github/, .claude/, CLAUDE.md
# Exits non-zero when any unreplaced {{...}} tokens are found.

set -euo pipefail

TARGET="${1:-.}"

# Paths to scan, relative to TARGET
SCAN_PATHS=(".github" ".claude" "CLAUDE.md")

found=0

for path in "${SCAN_PATHS[@]}"; do
  full_path="$TARGET/$path"
  [[ -e "$full_path" ]] || continue

  while IFS= read -r line; do
    # line format from grep: <file>:<lineno>:<match>
    file="${line%%:*}"
    rest="${line#*:}"
    lineno="${rest%%:*}"
    content="${rest#*:}"

    # Extract every {{PLACEHOLDER}} token from the line (uppercase letters and underscores only)
    tokens=$(grep -oE '\{\{[A-Z_][A-Z0-9_]*\}\}' <<< "$content" | sort -u | tr '\n' ' ')

    printf '%s:%s: %s\n' "$file" "$lineno" "$tokens"
    found=1
  done < <(grep -rHn --include="*.md" --include="*.yml" --include="*.yaml" \
                     --include="*.json" --include="*.hcl" --include="*.tf" \
                     -E '\{\{[A-Z_][A-Z0-9_]*\}\}' "$full_path" 2>/dev/null || true)
done

if [[ "$found" -ne 0 ]]; then
  echo ""
  echo "ERROR: Unreplaced {{PLACEHOLDER}} tokens found. Replace them before use." >&2
  exit 1
fi

echo "OK: No unreplaced placeholders found."
