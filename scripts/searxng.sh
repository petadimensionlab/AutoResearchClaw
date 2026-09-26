#!/usr/bin/env bash
# Ensure a self-hosted SearXNG instance is running for local-deep-research.
#
# - Reuses a healthy running instance when its JSON API responds.
# - Handles port conflicts: if the desired host port is taken by another
#   process, it scans upward for a free port and recreates the container there.
# - Persists the chosen port in "$SEARXNG_DIR/.env" and syncs the LDR
#   deep-research instance URL in "$LDR_ENV_FILE".
#
# Usage:
#   scripts/searxng.sh [--port N] [--force]
#
# Env overrides:
#   SEARXNG_DIR (default ~/workspace/research/searxng)
#   LDR_ENV_FILE (default ~/workspace/research/local-deep-research/.env.ds4)
#   SEARXNG_PORT (fallback preferred port), SEARXNG_PORT_SCAN_MAX (default 8130)
set -euo pipefail

SEARXNG_DIR="${SEARXNG_DIR:-$HOME/workspace/research/searxng}"
LDR_ENV_FILE="${LDR_ENV_FILE:-$HOME/workspace/research/local-deep-research/.env.ds4}"
CONTAINER="${SEARXNG_CONTAINER:-searxng}"
PORT_SCAN_MAX="${SEARXNG_PORT_SCAN_MAX:-8130}"
INSTANCE_KEY="LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_INSTANCE_URL"

FORCE=0
DESIRED=""
while [ $# -gt 0 ]; do
  case "$1" in
    --port) DESIRED="${2:-}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

port_in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
searxng_healthy() {
  curl -fsS -m 5 "http://localhost:$1/search?q=ok&format=json" \
    -H "User-Agent: searxng-healthcheck" >/dev/null 2>&1
}
container_running() {
  docker ps --filter "name=^/${CONTAINER}$" --format '{{.Names}}' | grep -q .
}

if [ -z "$DESIRED" ] && [ -f "$SEARXNG_DIR/.env" ]; then
  DESIRED="$(sed -n 's/^SEARXNG_PORT=//p' "$SEARXNG_DIR/.env" | head -1)"
fi
[ -n "$DESIRED" ] || DESIRED="${SEARXNG_PORT:-8080}"

PORT="$DESIRED"

if [ "$FORCE" -eq 0 ] && container_running && searxng_healthy "$PORT"; then
  echo "SearXNG already healthy on port $PORT"
else
  if port_in_use "$PORT"; then
    if container_running; then
      echo "Port $PORT is held by the running SearXNG container — recreating."
    else
      echo "Port $PORT is in use by another process — scanning for a free port…"
    fi
    found=""
    scan=$((PORT + 1))
    while [ "$scan" -le "$PORT_SCAN_MAX" ]; do
      if ! port_in_use "$scan"; then found="$scan"; break; fi
      scan=$((scan + 1))
    done
    if [ -z "$found" ]; then
      echo "No free port in $((PORT + 1))..$PORT_SCAN_MAX" >&2
      exit 1
    fi
    PORT="$found"
    echo "Selected free port: $PORT"
  fi

  printf 'SEARXNG_PORT=%s\n' "$PORT" > "$SEARXNG_DIR/.env"
  ( cd "$SEARXNG_DIR" && docker compose up -d --force-recreate >/dev/null )

  printf 'Waiting for SearXNG on %s' "$PORT"
  healthy=0
  for _ in $(seq 1 40); do
    if searxng_healthy "$PORT"; then healthy=1; break; fi
    printf '.'; sleep 3
  done
  printf '\n'
  if [ "$healthy" -ne 1 ]; then
    echo "SearXNG did not become healthy on port $PORT" >&2
    exit 1
  fi
  echo "SearXNG up on port $PORT"
fi

if [ -f "$LDR_ENV_FILE" ]; then
  tmp="$(mktemp)"
  if grep -q "^${INSTANCE_KEY}=" "$LDR_ENV_FILE"; then
    sed "s|^${INSTANCE_KEY}=.*|${INSTANCE_KEY}=http://localhost:${PORT}|" \
      "$LDR_ENV_FILE" > "$tmp"
  else
    cat "$LDR_ENV_FILE" > "$tmp"
    printf '%s=http://localhost:%s\n' "$INSTANCE_KEY" "$PORT" >> "$tmp"
  fi
  mv "$tmp" "$LDR_ENV_FILE"
  echo "Synced LDR instance URL → http://localhost:$PORT ($LDR_ENV_FILE)"
else
  echo "LDR env file not found ($LDR_ENV_FILE) — instance URL: http://localhost:$PORT"
fi
