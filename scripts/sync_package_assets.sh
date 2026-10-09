#!/usr/bin/env bash
# Sync SPA + LLM example config into the Python package tree for wheel builds.
# Source of truth: frontend/public and config/ — run before `python -m build`.
#
#   ./scripts/sync_package_assets.sh            # mirror source of truth → package
#   ./scripts/sync_package_assets.sh --adopt    # first pull package-side edits back
#   ./scripts/sync_package_assets.sh --force    # discard package-side edits
#
# The guard exists because atlas/_static is what production actually serves, so
# people do edit it directly: the P4 layer toggles lived only there, and this
# script's --delete would have silently erased them.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/frontend/public"
PKG="$ROOT/atlas/_static"

ADOPT=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --adopt) ADOPT=1 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown flag: $arg (see --help)" >&2; exit 2 ;;
  esac
done

# Files the package tree would lose: present only there, or edited there more
# recently than the copy in the source of truth.
package_only_changes() {
  [[ -d "$PKG" ]] || return 0
  local file rel src
  while IFS= read -r file; do
    rel="${file#"$PKG"/}"
    src="$SRC/$rel"
    if [[ ! -f "$src" ]]; then
      echo "$rel"
    elif ! cmp -s "$file" "$src" && [[ ! "$src" -nt "$file" ]]; then
      # Differs and the source of truth is NOT the newer side: either the edit
      # was made here, or the two are indistinguishable by timestamp. Both are
      # cases where overwriting could lose work, so ask.
      echo "$rel"
    fi
  done < <(find "$PKG" -type f)
}

# mapfile is bash 4+; macOS ships 3.2, so keep this newline-delimited.
DRIFT="$(package_only_changes)"
DRIFT_N=0
[[ -n "$DRIFT" ]] && DRIFT_N="$(printf '%s\n' "$DRIFT" | wc -l | tr -d ' ')"

if [[ "$DRIFT_N" -gt 0 ]]; then
  if [[ "$ADOPT" -eq 1 ]]; then
    echo "Adopting ${DRIFT_N} package-side edit(s) into frontend/public:"
    while IFS= read -r rel; do
      [[ -n "$rel" ]] || continue
      echo "  <- $rel"
      mkdir -p "$SRC/$(dirname "$rel")"
      cp -p "$PKG/$rel" "$SRC/$rel"
    done <<< "$DRIFT"
  elif [[ "$FORCE" -eq 1 ]]; then
    echo "Discarding ${DRIFT_N} package-side edit(s) (--force):"
    printf '  x %s\n' "$DRIFT"
  else
    echo "atlas/_static has ${DRIFT_N} change(s) that frontend/public does not:" >&2
    printf '  %s\n' "$DRIFT" >&2
    echo >&2
    echo "atlas/_static is a build artifact of frontend/public, and syncing" >&2
    echo "would delete these. Re-run with --adopt to move them into the source" >&2
    echo "of truth first, or --force to discard them." >&2
    exit 1
  fi
fi

mkdir -p "$PKG" "$ROOT/atlas/_config"
rsync -a --delete "$SRC/" "$PKG/"
cp -f "$ROOT/config/model_providers.example.yaml" "$ROOT/atlas/_config/"
echo "synced → atlas/_static + atlas/_config"
