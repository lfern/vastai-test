#!/usr/bin/env bash
# Ejecuta el CLI de Vast.ai dentro del contenedor (perfil vast).
# Uso: _run.sh vastai <subcomando> [args...]
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
exec docker compose --profile vast run --rm vastai "$@"
