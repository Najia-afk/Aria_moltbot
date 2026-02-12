#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
HOOK_DIR="$ROOT_DIR/.git/hooks"

mkdir -p "$HOOK_DIR"
cp "$ROOT_DIR/scripts/pre-commit-hook.sh" "$HOOK_DIR/pre-commit"
chmod +x "$HOOK_DIR/pre-commit"

echo "Installed pre-commit hook at $HOOK_DIR/pre-commit"
