#!/usr/bin/env bash
# Buscar tipos de instancia (misma lógica que el buscador en la web).
# Ejemplos:
#   ./search-offers.sh
#   ./search-offers.sh "gpu_ram>=20 num_gpus=1"
#   ./search-offers.sh "reliability>0.99 num_gpus>=4" --order num_gpus desc
# Ver filtros: https://cloud.vast.ai/cli/ y vastai search offers --help
exec "$(dirname "$0")/_run.sh" search offers "$@"
