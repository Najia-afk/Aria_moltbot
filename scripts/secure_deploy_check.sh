#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${ARIA_DIR}/stacks/brain/.env"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

[[ -f "$ENV_FILE" ]] || fail "Missing ${ENV_FILE}"
[[ "$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null || stat -c '%a' "$ENV_FILE")" == "600" ]] \
    || fail ".env permissions must be 600"

while IFS='=' read -r key value; do
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    export "$key=$value"
done < "$ENV_FILE"

for key in DB_PASSWORD WEB_SECRET_KEY LITELLM_MASTER_KEY ARIA_API_KEY ARIA_ADMIN_KEY \
    ARIA_LAN_BIND_ADDRESS ARIA_LAN_USER ARIA_LAN_PASSWORD_HASH NAS_OLLAMA_URL; do
    [[ -n "${!key:-}" ]] || fail "${key} is required"
done
[[ "${ARIA_ENV:-}" == "production" ]] || fail "ARIA_ENV must be production"
[[ "$ARIA_LAN_BIND_ADDRESS" != "0.0.0.0" && "$ARIA_LAN_BIND_ADDRESS" != "::" ]] \
    || fail "LAN bind address must be a specific interface address"
[[ "$ARIA_API_KEY" != "$ARIA_ADMIN_KEY" ]] || fail "API and admin keys must differ"
[[ "$ARIA_LAN_PASSWORD_HASH" == '$$apr1$$'* || "$ARIA_LAN_PASSWORD_HASH" == '$$2'* ]] \
    || fail "LAN password must be an htpasswd hash"

.venv/bin/python - "$NAS_OLLAMA_URL" <<'PY'
import ipaddress
import socket
import sys
from urllib.parse import urlparse

url = urlparse(sys.argv[1])
if url.scheme != "http" or not url.hostname or url.port != 11434:
    raise SystemExit("FAIL: NAS_OLLAMA_URL must be http://<private-host>:11434")
addresses = {item[4][0] for item in socket.getaddrinfo(url.hostname, url.port)}
if not addresses or any(not ipaddress.ip_address(address).is_private for address in addresses):
    raise SystemExit("FAIL: NAS_OLLAMA_URL must resolve only to private addresses")
PY
pass "NAS endpoint resolves privately"

.venv/bin/python - <<'PY'
from aria_models.loader import load_catalog, validate_models

errors = validate_models()
if errors:
    raise SystemExit("FAIL: " + "; ".join(errors))
catalog = load_catalog()
enabled = {
    model_id: entry for model_id, entry in catalog["models"].items()
    if entry.get("enabled", True)
}
if set(enabled) != {"nas_ollama", "embedding"}:
    raise SystemExit(f"FAIL: unexpected enabled models: {sorted(enabled)}")
if catalog["routing"]["fallbacks"] != ["litellm/nas_ollama"]:
    raise SystemExit("FAIL: fallback chain is not NAS-only")
PY
pass "model routing is NAS-only"

cd "${ARIA_DIR}/stacks/brain"
docker compose config --quiet
pass "Compose configuration is valid"

tags_file="$(mktemp)"
trap 'rm -f "$tags_file"' EXIT
curl -fsS --connect-timeout 3 --max-time 10 "${NAS_OLLAMA_URL}/api/tags" > "$tags_file" \
    || fail "NAS Ollama is not reachable at the configured private endpoint"
"${ARIA_DIR}/.venv/bin/python" -c 'import json,sys; names={m["name"].split(":")[0] for m in json.load(open(sys.argv[1])).get("models",[])}; required={"aria-primary","nomic-embed-text"}; missing=required-names; assert not missing, f"missing NAS models: {sorted(missing)}"' "$tags_file"
pass "NAS Ollama is reachable with required aliases"

if [[ "${NAS_BACKUP_ENABLED:-false}" == "true" ]]; then
    for key in NAS_BACKUP_HOST NAS_BACKUP_USER NAS_BACKUP_DIR NAS_BACKUP_SSH_KEY NAS_BACKUP_KNOWN_HOSTS; do
        [[ -n "${!key:-}" ]] || fail "${key} is required when NAS backup is enabled"
    done
    [[ -f "$NAS_BACKUP_SSH_KEY" ]] || fail "NAS backup SSH key is missing"
    [[ -s "$NAS_BACKUP_KNOWN_HOSTS" ]] || fail "NAS known_hosts file is missing or empty"
fi

pass "secure deployment preflight complete"