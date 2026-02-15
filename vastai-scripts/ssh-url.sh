#!/usr/bin/env bash
# Obtener la URL/comando SSH para conectar a una instancia.
# Uso: ./ssh-url.sh <instance_id>
# Luego: ssh -p <puerto> root@<host> (o el comando que muestre)
if [[ -z "$1" ]]; then
  echo "Uso: $0 <instance_id>"
  exit 1
fi
exec "$(dirname "$0")/_run.sh" ssh-url "$@"
