#!/usr/bin/env bash
# Listar tus instancias actuales.
exec "$(dirname "$0")/_run.sh" show instances "$@"
