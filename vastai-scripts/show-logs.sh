#!/usr/bin/env bash
# Solicita los logs de una instancia. Vast.ai los sube a S3 y devuelve una URL para descargarlos.
# Uso:
#   ./show-logs.sh <instance_id>                      # logs del contenedor
#   ./show-logs.sh <instance_id> --tail 500
#   ./show-logs.sh <instance_id> --daemon-logs true    # "extra logs" = logs del sistema/daemon
#   ./show-logs.sh <instance_id> --filter "error"
# La respuesta suele incluir result_url; descargar con: curl -o logs.txt "<URL>"
if [[ -z "$1" ]]; then
  echo "Uso: $0 <instance_id> [--tail N] [--filter patrón] [--daemon-logs true]"
  echo "  --daemon-logs true  = logs del sistema (lo que en la web llaman 'extra logs')"
  exit 1
fi
exec "$(dirname "$0")/_run.sh" logs "$@"
