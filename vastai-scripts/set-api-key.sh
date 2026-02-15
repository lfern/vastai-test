#!/usr/bin/env bash
# Login / Set API Key - Guarda la API key en vastai-config (persistida en el contenedor).
# Obtén la key en: https://cloud.vast.ai/cli/
# Uso: ./set-api-key.sh "tu-api-key"
set -e
KEY="${1:-}"
if [[ -z "$KEY" ]]; then
  echo "Uso: $0 \"tu-api-key\""
  echo "Obtén tu API key en: https://cloud.vast.ai/cli/ (Login / Set API Key)"
  exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
docker compose --profile vast run --rm vastai set api-key "$KEY"
echo "API key guardada en ./vastai-config/"
