#!/usr/bin/env bash
# Sync SPA + LLM example config into the Python package tree for wheel builds.
# Source of truth: frontend/public and config/ — run before `python -m build`.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/atlas/_static" "$ROOT/atlas/_config"
rsync -a --delete "$ROOT/frontend/public/" "$ROOT/atlas/_static/"
cp -f "$ROOT/config/model_providers.example.yaml" "$ROOT/atlas/_config/"
echo "synced → atlas/_static + atlas/_config"
