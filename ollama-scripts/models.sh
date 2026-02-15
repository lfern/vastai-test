#!/usr/bin/env bash
#
# models.sh - Listar, descargar (añadir) y eliminar modelos de Ollama.
#
# Uso:
#   ./models.sh list                    # listar modelos
#   ./models.sh pull llama3.3           # descargar modelo
#   ./models.sh pull llama3.1:8b        # descargar variante con tag
#   ./models.sh delete llama3.1:8b      # eliminar modelo
#   ./models.sh add llama3.3            # alias de pull
#   ./models.sh remove llama3.3         # alias de delete
#
# Variables: OLLAMA_URL (default: http://localhost:11434)
#

set -e
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

usage() {
  echo "Uso: $0 <comando> [modelo]"
  echo ""
  echo "Comandos:"
  echo "  list, ls, -l           Listar modelos instalados"
  echo "  pull, add, p           Descargar un modelo (ej: llama3.3, llama3.1:8b)"
  echo "  delete, remove, rm, d  Eliminar un modelo"
  echo ""
  echo "Ejemplos:"
  echo "  $0 list"
  echo "  $0 pull llama3.3"
  echo "  $0 delete llama3.1:8b"
  exit 1
}

list_models() {
  echo "Modelos en Ollama (${OLLAMA_URL}):"
  echo ""
  local resp
  resp=$(curl -s "${OLLAMA_URL}/api/tags") || {
    echo "Error: no se pudo conectar con Ollama. ¿Está corriendo?" >&2
    exit 1
  }
  if command -v jq &>/dev/null; then
    local count
    count=$(echo "$resp" | jq '.models | length')
    if [[ "$count" -eq 0 ]]; then
      echo "  (ningún modelo instalado)"
      echo ""
      echo "Descarga uno con: $0 pull <nombre>"
      return
    fi
    echo "$resp" | jq -r '.models[] | "  \(.name)  (\(.size / 1024 / 1024 / 1024 | floor) GB)"'
  else
    # Sin jq: extraer nombres con grep/sed
    if ! echo "$resp" | grep -q '"models"'; then
      echo "  (respuesta inesperada o ningún modelo)"
      return
    fi
    echo "$resp" | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"$//' | sed 's/^/  /'
  fi
  echo ""
}

pull_model() {
  local name="$1"
  if [[ -z "$name" ]]; then
    echo "Error: indica el nombre del modelo. Ej: $0 pull llama3.3" >&2
    exit 1
  fi
  echo "Descargando modelo: $name"
  echo ""
  curl -s -N -X POST "${OLLAMA_URL}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$name\"}" | while IFS= read -r line; do
    if [[ -n "$line" ]]; then
      if command -v jq &>/dev/null; then
        local status digest
        status=$(echo "$line" | jq -r '.status // empty')
        digest=$(echo "$line" | jq -r '.digest // empty')
        if [[ -n "$status" ]]; then
          echo "  $status"
        fi
        if [[ -n "$digest" ]]; then
          echo "  digest: $digest"
        fi
      else
        echo "  $line"
      fi
    fi
  done
  echo ""
  echo "Hecho. Lista actual:"
  list_models
}

delete_model() {
  local name="$1"
  if [[ -z "$name" ]]; then
    echo "Error: indica el nombre del modelo a eliminar. Ej: $0 delete llama3.1:8b" >&2
    exit 1
  fi
  echo "Eliminando modelo: $name"
  local resp
  resp=$(curl -s -w "\n%{http_code}" -X DELETE "${OLLAMA_URL}/api/delete" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$name\"}")
  local code
  code=$(echo "$resp" | tail -n1)
  local body
  body=$(echo "$resp" | sed '$d')
  if [[ "$code" -ge 200 && "$code" -lt 300 ]]; then
    echo "Modelo '$name' eliminado."
    echo ""
    echo "Modelos restantes:"
    list_models
  else
    echo "Error al eliminar (HTTP $code): $body" >&2
    exit 1
  fi
}

# Main
CMD="${1:-}"
MODEL="${2:-}"

case "$CMD" in
  list|ls|-l)
    list_models
    ;;
  pull|add|p)
    pull_model "$MODEL"
    ;;
  delete|remove|rm|d)
    delete_model "$MODEL"
    ;;
  "")
    usage
    ;;
  *)
    echo "Comando desconocido: $CMD" >&2
    usage
    ;;
esac
