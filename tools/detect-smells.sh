#!/usr/bin/env bash
# =============================================================================
# detect-smells.sh — IaC Code Smell Detector
#
# Scans a Terraform workspace for common anti-patterns and prints each finding
# with the affected file path, line number, and a plain-English description.
#
# Usage:
#   bash detect-smells.sh [WORKSPACE_PATH]
#
#   WORKSPACE_PATH defaults to the current directory.
#
# Output format (one line per finding):
#   SMELL  <anti-pattern-id>  <file>:<line>  <description>
#   PASS   <anti-pattern-id>  <description>
#
# Exit codes:
#   0 — no smells detected
#   1 — one or more smells detected
# =============================================================================

set -uo pipefail

ROOT="${1:-.}"
SMELLS=0
CHECKS=0

# ── Helpers ───────────────────────────────────────────────────────────────────

_smell() {
  # $1=id  $2=file:line  $3=description
  printf 'SMELL  %-38s  %-50s  %s\n' "$1" "$2" "$3"
  SMELLS=$(( SMELLS + 1 ))
}

_pass() {
  # $1=id  $2=description
  printf 'PASS   %-38s  %s\n' "$1" "$2"
}

_title() {
  printf '\n── %s ──\n' "$1"
}

# Enumerate .tf files, excluding the .terraform provider cache
_tf_files() {
  find "$ROOT" -name "*.tf" ! -path '*/.terraform/*' 2>/dev/null
}

# Enumerate .hcl files, excluding the .terraform provider cache
_hcl_files() {
  find "$ROOT" -name "*.hcl" ! -path '*/.terraform/*' 2>/dev/null
}

# Enumerate unique directories that contain at least one .tf file
_module_dirs() {
  _tf_files | xargs -r -I{} dirname {} 2>/dev/null | sort -u
}

# =============================================================================
printf '=%.0s' {1..80}; printf '\n'
printf ' IaC Code Smell Detector\n'
printf ' Workspace : %s\n' "$(realpath "$ROOT" 2>/dev/null || echo "$ROOT")"
printf ' Timestamp : %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date)"
printf '=%.0s' {1..80}; printf '\n'

# =============================================================================
# 1. Hardcoded secrets / credentials
# =============================================================================
_title "1. Hardcoded secrets / credentials"
CHECKS=$(( CHECKS + 1 ))
_smell_found=0

# Match:  key_name = "literal_value"
# where key_name looks like a credential field.
# Exclude:
#   - Lines that are Terraform comments (#)
#   - Variable/description declarations
#   - Values that are interpolations (${...}) or variable references (var.)
_SECRET_RE='(password|passwd|secret|api_key|access_key|private_key|token|auth_key|connection_string|client_secret)[[:space:]]*=[[:space:]]*"[^"][^"]*"'

while IFS= read -r file; do
  while IFS=: read -r lineno content; do
    # Skip pure variable/output/description declarations and interpolated values
    echo "$content" | grep -qiE '^[[:space:]]*(variable|output)[[:space:]]+"' && continue
    echo "$content" | grep -qE '"[[:space:]]*\$\{' && continue
    echo "$content" | grep -qE '"[[:space:]]*(var\.|local\.|data\.)' && continue
    echo "$content" | grep -qE 'description[[:space:]]*=' && continue
    _smell "hardcoded-secrets" "${file}:${lineno}" "Possible hardcoded credential in assignment"
    _smell_found=1
  done < <(grep -inE "$_SECRET_RE" "$file" 2>/dev/null | grep -v '^[[:space:]]*#' || true)
done < <(_tf_files; _hcl_files)

[ "$_smell_found" -eq 0 ] && _pass "hardcoded-secrets" "No hardcoded secrets detected in .tf / .hcl files"

# =============================================================================
# 2. Missing tests
# =============================================================================
_title "2. Missing tests"
CHECKS=$(( CHECKS + 1 ))
_smell_found=0

while IFS= read -r mdir; do
  res_count=$(grep -rc '^resource ' "$mdir" --include="*.tf" 2>/dev/null \
    | awk -F: '{s+=$2} END {print s+0}')
  [ "$res_count" -eq 0 ] && continue

  # Check for test files in this module directory and its subdirectories
  module_test_count=$(find "$mdir" \( -name "*.tftest.hcl" -o -name "*_test.go" \) \
    ! -path '*/.terraform/*' 2>/dev/null | wc -l)

  if [ "$module_test_count" -eq 0 ]; then
    _smell "missing-tests" "${mdir}/" \
      "Module has ${res_count} resource(s) but no .tftest.hcl or *_test.go found"
    _smell_found=1
  fi
done < <(_module_dirs)

[ "$_smell_found" -eq 0 ] && \
  _pass "missing-tests" "All resource-containing modules have test files"

# =============================================================================
# 3. Monolithic modules (too many resources in one module)
# =============================================================================
_title "3. Monolithic modules"
CHECKS=$(( CHECKS + 1 ))
_smell_found=0
RESOURCE_THRESHOLD=10

while IFS= read -r mdir; do
  count=$(grep -rc '^resource ' "$mdir" --include="*.tf" 2>/dev/null \
    | awk -F: '{s+=$2} END {print s+0}')
  if [ "$count" -ge "$RESOURCE_THRESHOLD" ]; then
    _smell "monolithic-module" "${mdir}/" \
      "Module contains ${count} resource blocks (threshold: ${RESOURCE_THRESHOLD}) — consider splitting"
    _smell_found=1
  fi
done < <(_module_dirs)

[ "$_smell_found" -eq 0 ] && \
  _pass "monolithic-module" "No monolithic modules detected (threshold: ${RESOURCE_THRESHOLD} resources/module)"

# =============================================================================
# 4. Missing state backend configuration
# =============================================================================
_title "4. Missing state backend configuration"
CHECKS=$(( CHECKS + 1 ))

tf_count=$(find "$ROOT" -name "*.tf" ! -path '*/.terraform/*' 2>/dev/null | wc -l)

if [ "$tf_count" -gt 0 ]; then
  backend_files=$(grep -rl 'backend[[:space:]]*"' "$ROOT" --include="*.tf" 2>/dev/null || true)
  cloud_files=$(grep -rl '^[[:space:]]*cloud[[:space:]]*{' "$ROOT" --include="*.tf" 2>/dev/null || true)

  if [ -z "$backend_files" ] && [ -z "$cloud_files" ]; then
    _smell "missing-backend" "${ROOT}/" \
      "No remote state backend or Terraform Cloud block found — local state only"
  else
    _pass "missing-backend" "Remote state backend / Terraform Cloud block found"
  fi
else
  _pass "missing-backend" "No .tf files found — backend check skipped"
fi

# =============================================================================
# 5. No tagging / labeling standard
# =============================================================================
_title "5. No tagging / labeling standard"
CHECKS=$(( CHECKS + 1 ))
_smell_found=0

while IFS= read -r mdir; do
  res_count=$(grep -rc '^resource ' "$mdir" --include="*.tf" 2>/dev/null \
    | awk -F: '{s+=$2} END {print s+0}')
  [ "$res_count" -eq 0 ] && continue

  tag_count=$(grep -r '\btags\b\|\blabels\b' "$mdir" --include="*.tf" 2>/dev/null \
    | grep -v '^[[:space:]]*#' | wc -l)

  if [ "$tag_count" -eq 0 ]; then
    _smell "no-tagging-standard" "${mdir}/" \
      "Module has ${res_count} resource(s) but no 'tags' or 'labels' attribute found"
    _smell_found=1
  fi
done < <(_module_dirs)

[ "$_smell_found" -eq 0 ] && \
  _pass "no-tagging-standard" "Tagging/labeling found in all resource-containing modules"

# =============================================================================
# 6. Duplicated code across directories
# =============================================================================
_title "6. Duplicated code across directories"
CHECKS=$(( CHECKS + 1 ))
_smell_found=0

# Check for .tf files with identical content appearing in two or more directories.
# Focus on files that are commonly copy-pasted between environment directories.
_cksum_tmp=$(mktemp)
trap 'rm -f "$_cksum_tmp"' EXIT

while IFS= read -r file; do
  fname=$(basename "$file")
  # Only flag files that are canonical module files — these should NOT be duplicated
  [[ "$fname" =~ ^(variables|locals|versions|main|outputs)\.tf$ ]] || continue
  if command -v md5sum &>/dev/null; then
    cksum=$(md5sum "$file" 2>/dev/null | cut -d' ' -f1)
  elif command -v md5 &>/dev/null; then
    cksum=$(md5 -q "$file" 2>/dev/null)
  else
    continue
  fi

  key="${fname}::${cksum}"
  prev=$(grep "^${key}	" "$_cksum_tmp" 2>/dev/null | head -1 | cut -f2)
  if [ -n "$prev" ]; then
    _smell "duplicated-code" "$file" \
      "Identical to ${prev} — consider a shared module or DRY envcommon pattern"
    _smell_found=1
  else
    printf '%s\t%s\n' "$key" "$file" >> "$_cksum_tmp"
  fi
done < <(_tf_files | sort)

[ "$_smell_found" -eq 0 ] && \
  _pass "duplicated-code" "No duplicate canonical .tf files detected across directories"

# =============================================================================
# 7. Missing provider version constraints
# =============================================================================
_title "7. Missing provider version constraints"
CHECKS=$(( CHECKS + 1 ))
_smell_found=0

tf_count=$(find "$ROOT" -name "*.tf" ! -path '*/.terraform/*' 2>/dev/null | wc -l)

if [ "$tf_count" -gt 0 ]; then
  req_provider_files=$(grep -rl 'required_providers' "$ROOT" --include="*.tf" 2>/dev/null || true)

  if [ -z "$req_provider_files" ]; then
    _smell "missing-provider-version" "${ROOT}/" \
      "No required_providers block found — provider versions are completely unpinned"
    _smell_found=1
  else
    while IFS= read -r file; do
      if command -v python3 &>/dev/null; then
        # Use Python for accurate HCL block parsing
        missing_providers=$(python3 - "$file" <<'PYEOF'
import sys, re

try:
    content = open(sys.argv[1]).read()
except OSError as e:
    print(f"detect-smells: cannot read {sys.argv[1]}: {e}", file=sys.stderr)
    sys.exit(0)

# Find the required_providers block (handle nested braces)
start = content.find('required_providers')
if start == -1:
    sys.exit(0)

brace_start = content.find('{', start)
if brace_start == -1:
    sys.exit(0)

depth, i = 0, brace_start
while i < len(content):
    if content[i] == '{':
        depth += 1
    elif content[i] == '}':
        depth -= 1
        if depth == 0:
            break
    i += 1

block = content[brace_start+1:i]

# Each provider entry: name = { source = "..." [version = "..."] }
for pm in re.finditer(r'(\w+)\s*=\s*\{([^}]*)\}', block, re.DOTALL):
    pname = pm.group(1)
    pbody = pm.group(2)
    if re.search(r'\bsource\s*=', pbody) and not re.search(r'\bversion\s*=', pbody):
        print(pname)
PYEOF
        )
        if [ -n "$missing_providers" ]; then
          while IFS= read -r provider; do
            lineno=$(grep -Fn "$provider" "$file" 2>/dev/null | head -1 | cut -d: -f1)
            _smell "missing-provider-version" "${file}:${lineno:-?}" \
              "Provider '${provider}' has source but no version constraint in required_providers"
            _smell_found=1
          done <<< "$missing_providers"
        fi
      else
        # Fallback: compare count of source = vs version = lines inside required_providers
        sources=$(awk '/required_providers/{f=1} f && /source[[:space:]]*=/{c++} /^[[:space:]]*\}[[:space:]]*$/ && f{f=0} END{print c+0}' "$file")
        versions=$(awk '/required_providers/{f=1} f && /version[[:space:]]*=/{c++} /^[[:space:]]*\}[[:space:]]*$/ && f{f=0} END{print c+0}' "$file")
        if [ "$sources" -gt "$versions" ]; then
          _smell "missing-provider-version" "$file:?" \
            "Some providers in required_providers appear to be missing a version constraint"
          _smell_found=1
        fi
      fi
    done <<< "$req_provider_files"
  fi
fi

[ "$_smell_found" -eq 0 ] && \
  _pass "missing-provider-version" "All providers in required_providers have version constraints"

# =============================================================================
# 8. Missing .gitignore for Terraform artifacts
# =============================================================================
_title "8. Missing .gitignore for Terraform artifacts"
CHECKS=$(( CHECKS + 1 ))
_smell_found=0

GITIGNORE="${ROOT}/.gitignore"

tf_count=$(find "$ROOT" -name "*.tf" ! -path '*/.terraform/*' 2>/dev/null | wc -l)

if [ "$tf_count" -gt 0 ]; then
  if [ ! -f "$GITIGNORE" ]; then
    _smell "missing-gitignore" "${ROOT}/" \
      "No .gitignore found — Terraform cache and state files may be committed accidentally"
    _smell_found=1
  else
    for pattern in '.terraform/' '*.tfstate' '*.tfstate.backup'; do
      if ! grep -qF "$pattern" "$GITIGNORE" 2>/dev/null; then
        lineno=$(wc -l < "$GITIGNORE" 2>/dev/null || echo "?")
        _smell "missing-gitignore" "${GITIGNORE}:${lineno}" \
          "Missing gitignore entry: '${pattern}'"
        _smell_found=1
      fi
    done
  fi
fi

[ "$_smell_found" -eq 0 ] && \
  _pass "missing-gitignore" ".gitignore covers .terraform/, *.tfstate, and *.tfstate.backup"

# =============================================================================
# Summary
# =============================================================================
printf '\n'
printf '=%.0s' {1..80}; printf '\n'
printf ' Summary: %d smell(s) found across %d checks\n' "$SMELLS" "$CHECKS"
printf '=%.0s' {1..80}; printf '\n'

[ "$SMELLS" -gt 0 ] && exit 1
exit 0
