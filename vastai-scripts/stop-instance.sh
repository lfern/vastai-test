#!/usr/bin/env bash
# Parar una instancia en ejecución.
# Uso: ./stop-instance.sh <instance_id>
if [[ -z "$1" ]]; then
  echo "Uso: $0 <instance_id>"
  exit 1
fi
exec "$(dirname "$0")/_run.sh" stop instance "$@"
