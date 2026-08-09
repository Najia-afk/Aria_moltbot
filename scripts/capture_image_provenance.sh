#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${ARIA_DIR}/stacks/brain/docker-compose.yml"
VAULT_DIR="${VAULT_DIR:-${HOME}/aria_vault}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${VAULT_DIR}/release-evidence/${TIMESTAMP}"

command -v docker >/dev/null || { echo "ERROR: docker is required" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "ERROR: Docker engine is not running" >&2; exit 1; }
[[ -f "$COMPOSE_FILE" ]] || { echo "ERROR: Compose file not found" >&2; exit 1; }

umask 077
mkdir -p "$OUTPUT_DIR"

git -C "$ARIA_DIR" rev-parse HEAD > "${OUTPUT_DIR}/git-commit.txt"
git -C "$ARIA_DIR" status --short --branch > "${OUTPUT_DIR}/git-status.txt"
shasum -a 256 "$COMPOSE_FILE" > "${OUTPUT_DIR}/compose-source.sha256"
docker compose -f "$COMPOSE_FILE" config --images | sort -u > "${OUTPUT_DIR}/compose-images.txt"

printf 'container\timage\timage_id\tports\n' > "${OUTPUT_DIR}/running-containers.tsv"
docker ps --format '{{.Names}}\t{{.Image}}\t{{.ID}}\t{{.Ports}}' \
    | sort >> "${OUTPUT_DIR}/running-containers.tsv"

printf 'repository\timage_id\trepo_digests\tcreated\tsize_bytes\tos\tarchitecture\n' \
    > "${OUTPUT_DIR}/images.tsv"
while IFS= read -r image; do
    [[ -n "$image" ]] || continue
    if ! docker image inspect "$image" >/dev/null 2>&1; then
        printf '%s\tMISSING\t\t\t\t\t\n' "$image" >> "${OUTPUT_DIR}/images.tsv"
        continue
    fi
    docker image inspect "$image" --format \
        '{{.RepoTags}}|{{.Id}}|{{json .RepoDigests}}|{{.Created}}|{{.Size}}|{{.Os}}|{{.Architecture}}' \
        | awk -F'|' -v image="$image" 'BEGIN { OFS="\t" } { print image, $2, $3, $4, $5, $6, $7 }' \
        >> "${OUTPUT_DIR}/images.tsv"
done < "${OUTPUT_DIR}/compose-images.txt"

docker volume ls --format '{{.Name}}' | grep -E '(^|_)aria(_|$)|^brain_' | sort \
    > "${OUTPUT_DIR}/aria-volumes.txt" || true

(
    cd "$OUTPUT_DIR"
    shasum -a 256 ./* > SHA256SUMS
)

echo "Image provenance captured privately: ${OUTPUT_DIR}"