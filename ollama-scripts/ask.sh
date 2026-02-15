#!/usr/bin/env bash
#
# ask.sh - Envía una pregunta a Ollama y muestra la respuesta (bash + curl).
#
# Uso:
#   ./ask.sh "¿Qué es Python?"
#   ./ask.sh "Explica Docker" --model llama3.1:8b
#   ./ask.sh "Pregunta" --no-stream
#
# Requiere: curl. Opcional: jq (para respuestas streaming más limpias).
#

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
MODEL="${MODEL:-llama3.3}"
STREAM=true

# Parsear argumentos simples
QUESTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model|-m)
      MODEL="$2"
      shift 2
      ;;
    --url|-u)
      OLLAMA_URL="$2"
      shift 2
      ;;
    --no-stream)
      STREAM=false
      shift
      ;;
    --list-models|-l)
      echo "Modelos disponibles:"
      curl -s "${OLLAMA_URL}/api/tags" | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"$//' | sed 's/^/  - /'
      exit 0
      ;;
    *)
      QUESTION="$1"
      shift
      ;;
  esac
done

if [[ -z "$QUESTION" ]]; then
  echo "Uso: $0 \"tu pregunta\" [--model nombre] [--url url] [--no-stream]"
  echo "     $0 --list-models"
  exit 1
fi

# Escapar para JSON (comillas, backslash, saltos de línea)
escape_json() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g; s/\r/\\r/g; s/\n/\\n/g'
}
QUESTION_ESC=$(escape_json "$QUESTION")

if [[ "$STREAM" == true ]]; then
  # Streaming: cada línea es un JSON con "response"
  BODY="{\"model\":\"$MODEL\",\"prompt\":\"$QUESTION_ESC\",\"stream\":true}"
  curl -s -N -X POST "${OLLAMA_URL}/api/generate" \
    -H "Content-Type: application/json" \
    -d "$BODY" | while IFS= read -r line; do
      if [[ -n "$line" ]]; then
        # Extraer .response sin jq: asumimos formato {"response":"texto",...}
        if command -v jq &>/dev/null; then
          printf '%s' "$(echo "$line" | jq -r '.response // empty')"
        else
          # Fallback: imprimir la línea y filtrar "response" con sed (frágil si hay " en el texto)
          echo "$line" | sed -n 's/.*"response":"\([^"]*\)".*/\1/p' | tr -d '\n'
        fi
      fi
    done
  echo ""
else
  # Sin streaming: una sola respuesta JSON
  BODY="{\"model\":\"$MODEL\",\"prompt\":\"$QUESTION_ESC\",\"stream\":false}"
  RESP=$(curl -s -X POST "${OLLAMA_URL}/api/generate" \
    -H "Content-Type: application/json" \
    -d "$BODY")
  if command -v jq &>/dev/null; then
    echo "$RESP" | jq -r '.response // .error // "Error desconocido"'
  else
    # Fallback: buscar "response":"... hasta la siguiente "
    echo "$RESP" | grep -o '"response":"[^"]*"' | head -1 | sed 's/"response":"//;s/"$//'
  fi
fi
