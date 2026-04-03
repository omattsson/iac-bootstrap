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

if [[ ! -e "$TARGET" ]]; then
  echo "ERROR: Target path does not exist: $TARGET" >&2
  exit 1
fi

if [[ ! -d "$TARGET" ]]; then
  echo "ERROR: Target path is not a directory: $TARGET" >&2
  exit 1
fi

# Paths to scan, relative to TARGET
SCAN_PATHS=(".github" ".claude" "CLAUDE.md")

found=0

for path in "${SCAN_PATHS[@]}"; do
  full_path="$TARGET/$path"
  [[ -e "$full_path" ]] || continue

  while IFS= read -r line; do
    # line format from grep -Hn: <file>:<lineno>:<full line text>
    file="${line%%:*}"
    rest="${line#*:}"
    lineno="${rest%%:*}"
    content="${rest#*:}"

    # Extract every {{PLACEHOLDER}} token from the line (starts with an uppercase letter or underscore, followed by uppercase letters, digits, or underscores)
    while IFS= read -r token; do
      printf '%s:%s: %s\n' "$file" "$lineno" "$token"
    done < <(grep -oE '\{\{[A-Z_][A-Z0-9_]*\}\}' <<< "$content" | sort -u)
    found=1
  done < <(grep -rHn --include="*.md" --include="*.yml" --include="*.yaml" \
                     --include="*.json" --include="*.hcl" --include="*.tf" \
                     -E '\{\{[A-Z_][A-Z0-9_]*\}\}' "$full_path" || {
    rc=$?
    [[ $rc -eq 1 ]] || { echo "ERROR: grep failed scanning $full_path (exit $rc)" >&2; exit 1; }
  })
done

if [[ "$found" -ne 0 ]]; then
  echo ""
  echo "ERROR: Unreplaced {{PLACEHOLDER}} tokens found. Replace them before use." >&2
  exit 1
fi

echo "OK: No unreplaced placeholders found."
