#!/usr/bin/env bash
# Detalle de una instancia.
# Uso: ./show-instance.sh <instance_id>
if [[ -z "$1" ]]; then
  echo "Uso: $0 <instance_id>"
  exit 1
fi
exec "$(dirname "$0")/_run.sh" show instance "$@"
