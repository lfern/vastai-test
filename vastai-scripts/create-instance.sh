#!/usr/bin/env bash
# Crear una instancia (ID = oferta de search offers).
# Uso: ./create-instance.sh <offer_id> [--image IMAGE] [--disk GB] [--ssh] [opciones...]
# Ejemplo: ./create-instance.sh 37744 --image pytorch/pytorch --disk 32
# Ver: vastai create instance --help
if [[ -z "$1" ]]; then
  echo "Uso: $0 <offer_id> [--image IMAGE] [--disk GB] [--ssh] [--direct] ..."
  echo "Ejemplo: $0 37744 --image pytorch/pytorch --disk 32 --ssh --direct"
  exit 1
fi
exec "$(dirname "$0")/_run.sh" create instance "$@"
