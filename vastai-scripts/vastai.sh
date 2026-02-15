#!/usr/bin/env bash
# Pasar cualquier comando al CLI (para comandos no cubiertos por otros scripts).
# Uso: ./vastai.sh show user
#      ./vastai.sh search offers "gpu_ram>=24"
exec "$(dirname "$0")/_run.sh" "$@"
