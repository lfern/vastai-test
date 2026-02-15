#!/usr/bin/env bash
#
# chat.sh - Chat interactivo con Ollama (bash + curl).
# Cada mensaje se envía como prompt; no se mantiene historial de conversación.
#
# Uso:
#   ./chat.sh
#   MODEL=llama3.1:8b ./chat.sh
#
# Requiere: curl. Opcional: jq.
#

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
MODEL="${MODEL:-llama3.3}"

escape_json() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g; s/\n/\\n/g'
}

send_message() {
  local prompt
  prompt=$(escape_json "$1")
  local body="{\"model\":\"$MODEL\",\"prompt\":\"$prompt\",\"stream\":true}"
  curl -s -N -X POST "${OLLAMA_URL}/api/generate" \
    -H "Content-Type: application/json" \
    -d "$body" | while IFS= read -r line; do
      if [[ -n "$line" ]]; then
        if command -v jq &>/dev/null; then
          printf '%s' "$(echo "$line" | jq -r '.response // empty')"
        else
          echo "$line" | sed -n 's/.*"response":"\([^"]*\)".*/\1/p' | tr -d '\n'
        fi
      fi
    done
  echo ""
}

echo "=============================================="
echo "  Chat con Ollama  [Modelo: $MODEL]"
echo "=============================================="
echo "Escribe tu mensaje y Enter. Vacío o Ctrl+D para salir."
echo ""

while true; do
  printf "Tú > "
  read -r input || break
  [[ -z "$input" ]] && continue
  echo ""
  printf "Ollama > "
  send_message "$input"
  echo ""
done

echo ""
echo "Hasta luego."
