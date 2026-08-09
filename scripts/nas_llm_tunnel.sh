#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${ARIA_DIR}/stacks/brain/.env"

fail() { echo "ERROR: $*" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || fail "Missing ${ENV_FILE}"

while IFS='=' read -r key value; do
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    export "$key=$value"
done < "$ENV_FILE"

for key in NAS_LLM_SSH_HOST NAS_LLM_SSH_USER NAS_LLM_SSH_KEY NAS_LLM_SSH_KNOWN_HOSTS; do
    [[ -n "${!key:-}" ]] || fail "${key} is required"
done

NAS_LLM_SSH_PORT="${NAS_LLM_SSH_PORT:-22}"
NAS_LLM_TUNNEL_PORT="${NAS_LLM_TUNNEL_PORT:-11435}"
NAS_LLM_REMOTE_PORT="${NAS_LLM_REMOTE_PORT:-11434}"
CONTROL_DIR="${HOME}/aria_vault/run"
CONTROL_PATH="${CONTROL_DIR}/nas-llm-tunnel.sock"
mkdir -p "$CONTROL_DIR"
chmod 700 "$CONTROL_DIR"

[[ -f "$NAS_LLM_SSH_KEY" ]] || fail "Tunnel SSH key does not exist"
[[ -s "$NAS_LLM_SSH_KNOWN_HOSTS" ]] || fail "Pinned NAS known-hosts file is missing or empty"

target="${NAS_LLM_SSH_USER}@${NAS_LLM_SSH_HOST}"
ssh_options=(
    -p "$NAS_LLM_SSH_PORT"
    -i "$NAS_LLM_SSH_KEY"
    -o BatchMode=yes
    -o IdentitiesOnly=yes
    -o StrictHostKeyChecking=yes
    -o "UserKnownHostsFile=${NAS_LLM_SSH_KNOWN_HOSTS}"
    -o ExitOnForwardFailure=yes
    -o ServerAliveInterval=30
    -o ServerAliveCountMax=3
    -S "$CONTROL_PATH"
)

case "${1:-check}" in
    start)
        if ssh "${ssh_options[@]}" -O check "$target" >/dev/null 2>&1; then
            echo "NAS LLM tunnel is already running"
            exit 0
        fi
        rm -f "$CONTROL_PATH"
        ssh "${ssh_options[@]}" -M -fN \
            -L "127.0.0.1:${NAS_LLM_TUNNEL_PORT}:127.0.0.1:${NAS_LLM_REMOTE_PORT}" \
            "$target"
        "$0" check
        ;;
    check)
        ssh "${ssh_options[@]}" -O check "$target" >/dev/null 2>&1 \
            || fail "NAS LLM tunnel is not running"
        curl -fsS --connect-timeout 2 --max-time 5 \
            "http://127.0.0.1:${NAS_LLM_TUNNEL_PORT}/api/tags" >/dev/null \
            || fail "Tunnel is running but Ollama is unavailable"
        echo "NAS LLM tunnel is healthy"
        ;;
    stop)
        ssh "${ssh_options[@]}" -O exit "$target" >/dev/null 2>&1 || true
        rm -f "$CONTROL_PATH"
        echo "NAS LLM tunnel stopped"
        ;;
    *)
        echo "Usage: $0 {start|check|stop}" >&2
        exit 2
        ;;
esac