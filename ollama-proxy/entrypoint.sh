#!/bin/sh
# Escribe la API key de Vast.ai desde la variable de entorno al fichero que espera el CLI.
# vast.py hace os.makedirs() sin exist_ok=True, así que aseguramos que el dir existe
# antes de que el módulo se importe por primera vez.
set -e

VASTAI_KEY_FILE="/root/.config/vastai/vast_api_key"

if [ -n "$VAST_API_KEY" ]; then
    mkdir -p "$(dirname "$VASTAI_KEY_FILE")"
    printf '%s' "$VAST_API_KEY" > "$VASTAI_KEY_FILE"
    echo "[entrypoint] VAST_API_KEY escrita en $VASTAI_KEY_FILE"
else
    echo "[entrypoint] ADVERTENCIA: VAST_API_KEY no definida — el CLI de Vast.ai no funcionará"
fi

exec uvicorn main:app --host 0.0.0.0 --port 11434
