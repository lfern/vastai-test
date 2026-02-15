#!/usr/bin/env bash
# Destruir una instancia (irreversible, borra datos).
# Uso: ./destroy-instance.sh <instance_id>
if [[ -z "$1" ]]; then
  echo "Uso: $0 <instance_id>"
  exit 1
fi
exec "$(dirname "$0")/_run.sh" destroy instance "$@"
