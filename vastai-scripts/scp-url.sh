#!/usr/bin/env bash
# URL/ayuda para SCP (copiar archivos con scp).
# Uso: ./scp-url.sh <instance_id>
exec "$(dirname "$0")/_run.sh" scp-url "$@"
