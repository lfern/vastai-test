#!/usr/bin/env bash
# Ejecutar comando en una instancia (ls, rm, du según la doc).
# Uso: ./execute.sh <instance_id> 'ls -la'
#      ./execute.sh <instance_id> 'rm /path/file'
#      ./execute.sh <instance_id> 'du -d2 -h'
if [[ -z "$1" || -z "$2" ]]; then
  echo "Uso: $0 <instance_id> '<comando>'"
  echo "Comandos soportados en la instancia: ls, rm, du (y otros bash permitidos)."
  exit 1
fi
exec "$(dirname "$0")/_run.sh" execute "$@"
