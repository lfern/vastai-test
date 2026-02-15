#!/usr/bin/env bash
# Arrancar una instancia parada.
# Uso: ./start-instance.sh <instance_id>
if [[ -z "$1" ]]; then
  echo "Uso: $0 <instance_id>"
  exit 1
fi
exec "$(dirname "$0")/_run.sh" start instance "$@"
