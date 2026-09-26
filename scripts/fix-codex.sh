#!/usr/bin/env bash
# Repair a broken global @openai/codex (npm) install.
#
# Symptom this fixes:
#   spawn .../@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/codex/codex ENOENT
#   Version: error: Command failed: codex --version
#
# Cause: the platform binary lives at vendor/<triple>/bin/codex in current
# releases, but a launcher / cached resolution may look for vendor/<triple>/codex/codex
# (or vice versa). This script finds the real binary and makes BOTH paths resolve.
#
# Usage:
#   scripts/fix-codex.sh              # diagnose + add compatibility symlinks
#   scripts/fix-codex.sh --reinstall  # clean reinstall first, then verify
set -euo pipefail

REINSTALL=0
[ "${1:-}" = "--reinstall" ] && REINSTALL=1

command -v npm >/dev/null 2>&1 || { echo "error: npm not found on PATH" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "error: node not found on PATH" >&2; exit 1; }

ROOT="$(npm root -g)"
PKG="$ROOT/@openai/codex"
echo "node: $(node --version)  npm: $(npm --version)"
echo "global root: $ROOT"

if [ "$REINSTALL" -eq 1 ]; then
  echo "reinstalling @openai/codex@latest (do not omit optional deps)…"
  npm install -g @openai/codex@latest
fi

if [ ! -d "$PKG" ]; then
  echo "codex not installed under $ROOT — installing @openai/codex@latest…"
  npm install -g @openai/codex@latest
fi

OS="$(uname -s)"; ARCH="$(uname -m)"
TRIPLE=""; PKGDIR=""
case "$OS" in
  Darwin) case "$ARCH" in
      arm64)  TRIPLE="aarch64-apple-darwin"; PKGDIR="codex-darwin-arm64" ;;
      x86_64) TRIPLE="x86_64-apple-darwin";  PKGDIR="codex-darwin-x64" ;;
    esac ;;
  Linux) case "$ARCH" in
      aarch64|arm64) TRIPLE="aarch64-unknown-linux-musl"; PKGDIR="codex-linux-arm64" ;;
      x86_64)        TRIPLE="x86_64-unknown-linux-musl";  PKGDIR="codex-linux-x64" ;;
    esac ;;
  *) echo "error: unsupported OS: $OS" >&2; exit 1 ;;
esac
[ -n "$TRIPLE" ] || { echo "error: unsupported arch: $ARCH" >&2; exit 1; }

V="$PKG/node_modules/@openai/$PKGDIR/vendor/$TRIPLE"
echo "vendor path: $V"

if [ ! -d "$V" ]; then
  echo "platform package missing ($V) — reinstalling @openai/codex@latest…"
  npm install -g @openai/codex@latest
fi

# Locate the real binary (either layout).
BIN=""
for candidate in "$V/bin/codex" "$V/codex/codex"; do
  if [ -f "$candidate" ] && [ -x "$candidate" ]; then BIN="$candidate"; break; fi
done
if [ -z "$BIN" ]; then
  echo "error: no executable codex binary found under $V" >&2
  find "$V" -maxdepth 3 -name 'codex*' 2>/dev/null | sed 's/^/  /' >&2 || true
  echo "hint: reinstall with: npm install -g @openai/codex@latest" >&2
  exit 1
fi
echo "real binary: $BIN"

mkdir -p "$V/bin" "$V/codex"
if [ ! -e "$V/bin/codex" ]; then
  echo "creating: $V/bin/codex -> $BIN"; ln -sfn "$BIN" "$V/bin/codex"
fi
if [ ! -e "$V/codex/codex" ]; then
  echo "creating: $V/codex/codex -> $BIN"; ln -sfn "$BIN" "$V/codex/codex"
fi

echo "--- verify ---"
if command -v codex >/dev/null 2>&1; then
  codex --version || { echo "codex --version still failing; try: $0 --reinstall" >&2; exit 1; }
else
  echo "warning: 'codex' is not on PATH (global bin dir may not be exported)" >&2
fi
echo "OK"
