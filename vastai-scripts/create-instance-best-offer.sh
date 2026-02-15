#!/usr/bin/env bash
# Busca ofertas (query por defecto = README/salida), toma el primer ID y lanza create instance
# con los parámetros del README (Ollama + Portal + Jupyter).
#
# Uso:
#   ./create-instance-best-offer.sh
#   ./create-instance-best-offer.sh "dph<0.12 num_gpus=1 gpu_ram>24"   # otra query
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Query por defecto: misma búsqueda que en README/salida (RTX 3090, 1 GPU, >24GB VRAM, >32GB RAM, barato y fiable)
SEARCH_QUERY="${1:-dph<0.15 reliability>0.999 gpu_name=RTX_3090 num_gpus=1 gpu_ram>=24 cpu_ram>=32 disk_space>=32}"

echo "Buscando ofertas: $SEARCH_QUERY"
echo ""

SEARCH_OUTPUT=$("$SCRIPT_DIR/search-offers.sh" "$SEARCH_QUERY" -o dph --limit 1)
OFFER_ID=$(echo "$SEARCH_OUTPUT" | awk 'NR==2 {print $1}')

if [[ -z "$OFFER_ID" || ! "$OFFER_ID" =~ ^[0-9]+$ ]]; then
  echo "No se encontró ninguna oferta con esa búsqueda." >&2
  echo "Salida de búsqueda:" >&2
  echo "$SEARCH_OUTPUT" >&2
  exit 1
fi

echo "Mejor oferta (cabecera + línea):"
echo "$SEARCH_OUTPUT" | awk 'NR<=2'
echo ""
printf "¿Crear instancia con esta oferta? (s/n): "
read -r resp
case "$(echo "$resp" | tr '[:lower:]' '[:upper:]')" in
  S|SI|SÍ|Y|YES) ;;
  *) echo "Cancelado. No se creó la instancia."; exit 0 ;;
esac
echo ""
echo "Lanzando create instance (ID: $OFFER_ID)..."

exec "$SCRIPT_DIR/create-instance.sh" "$OFFER_ID" \
  --image vastai/ollama:0.15.4 \
  --env '-p 21434:21434 -e OLLAMA_MODEL=glm-4.7-flash -e PORTAL_CONFIG="localhost:1111:11111:/:Instance Portal|localhost:21434:11434:/:Ollama API|localhost:8080:18080:/:Jupyter|localhost:8080:8080:/terminals/1:Jupyter Terminal" -e OPEN_BUTTON_PORT=1111 -e OPEN_BUTTON_TOKEN=1 -e JUPYTER_DIR=/ -e DATA_DIRECTORY=/workspace/' \
  --onstart-cmd 'entrypoint.sh' \
  --disk 32
