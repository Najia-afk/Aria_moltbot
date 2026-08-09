#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${ARIA_DIR}/stacks/brain/.env"
ENV_EXAMPLE="${ARIA_DIR}/stacks/brain/.env.example"
VAULT_DIR="${VAULT_DIR:-${HOME}/aria_vault}"
CREDENTIAL_DIR="${VAULT_DIR}/credentials"

usage() {
    echo "Usage: $0 --nas-host HOST [--lan-address ADDRESS] [--lan-user USER]"
}

NAS_HOST=""
LAN_ADDRESS=""
LAN_USER="aria"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --nas-host) NAS_HOST="${2:-}"; shift 2 ;;
        --lan-address) LAN_ADDRESS="${2:-}"; shift 2 ;;
        --lan-user) LAN_USER="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

if [[ -z "$NAS_HOST" ]]; then
    echo "ERROR: --nas-host is required" >&2
    exit 2
fi

if [[ -z "$LAN_ADDRESS" ]]; then
    default_interface="$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')"
    LAN_ADDRESS="$(ipconfig getifaddr "$default_interface" 2>/dev/null || true)"
fi
if [[ -z "$LAN_ADDRESS" ]]; then
    echo "ERROR: Could not detect the LAN address; pass --lan-address" >&2
    exit 1
fi

[[ -f "$ENV_FILE" ]] || cp "$ENV_EXAMPLE" "$ENV_FILE"
chmod 600 "$ENV_FILE"
mkdir -p "$CREDENTIAL_DIR"
chmod 700 "$CREDENTIAL_DIR"
cp "$ENV_FILE" "${CREDENTIAL_DIR}/brain.env.before-secure-lan.$(date +%Y%m%d_%H%M%S)"
chmod 600 "${CREDENTIAL_DIR}"/brain.env.before-secure-lan.*

get_env() {
    awk -F= -v key="$1" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE"
}

set_env() {
    local key="$1" value="$2" temporary
    temporary="$(mktemp "${ENV_FILE}.XXXXXX")"
    awk -v key="$key" -v value="$value" '
        BEGIN { found = 0 }
        $0 ~ "^" key "=" { print key "=" value; found = 1; next }
        { print }
        END { if (!found) print key "=" value }
    ' "$ENV_FILE" > "$temporary"
    chmod 600 "$temporary"
    mv "$temporary" "$ENV_FILE"
}

generate_secret() {
    openssl rand -base64 48 | tr -d '\n/+=' | cut -c1-48
}

for key in ARIA_API_KEY ARIA_ADMIN_KEY; do
    if [[ -z "$(get_env "$key")" ]]; then
        set_env "$key" "$(generate_secret)"
    fi
done

lan_password="$(generate_secret)"
lan_hash="$(printf '%s' "$lan_password" | openssl passwd -apr1 -stdin)"
compose_lan_hash="${lan_hash//\$/\$\$}"
printf 'user=%s\npassword=%s\n' "$LAN_USER" "$lan_password" > "${CREDENTIAL_DIR}/aria_lan_login"
chmod 600 "${CREDENTIAL_DIR}/aria_lan_login"
unset lan_password

set_env ARIA_ENV production
set_env ARIA_LAN_BIND_ADDRESS "$LAN_ADDRESS"
set_env ARIA_LAN_USER "$LAN_USER"
set_env ARIA_LAN_PASSWORD_HASH "$compose_lan_hash"
set_env SERVICE_HOST "$LAN_ADDRESS"
set_env MAC_LAN_IP "$LAN_ADDRESS"
set_env NAS_OLLAMA_URL "http://${NAS_HOST}:11434"
set_env CORS_ALLOWED_ORIGINS "https://${LAN_ADDRESS}:$(get_env TRAEFIK_HTTPS_PORT)"

# The active privacy-first deployment must not retain usable cloud credentials.
set_env MOONSHOT_KIMI_KEY ""
set_env OPEN_ROUTER_KEY ""
set_env OPEN_ROUTER_KEY_DEEP ""

if [[ -f "${ARIA_DIR}/stacks/brain/certs/cert.pem" ]] && \
   ! openssl x509 -in "${ARIA_DIR}/stacks/brain/certs/cert.pem" -noout -ext subjectAltName 2>/dev/null | grep -Fq "IP Address:${LAN_ADDRESS}"; then
    rm -f "${ARIA_DIR}/stacks/brain/certs/cert.pem" "${ARIA_DIR}/stacks/brain/certs/key.pem"
fi

echo "Secure LAN configuration written to ${ENV_FILE}"
echo "LAN login stored with mode 0600 at ${CREDENTIAL_DIR}/aria_lan_login"
echo "Run scripts/secure_deploy_check.sh after SSH and Ollama are enabled on the NAS."