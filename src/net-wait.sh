#!/bin/bash
# net-wait.sh — espera a que haya DNS/Internet antes de ejecutar un comando.
# Uso: net-wait.sh <segundos_max> <comando...>
# Sale con 75 (EX_TEMPFAIL) si nunca hubo red: el job no corre en vacío.

MAX=${1:-300}; shift
LOG=${NETWAIT_LOG:-$(dirname "$0")/net-wait.log}
PROBE_HOST=${NETWAIT_HOST:-syndication.twitter.com}
DEADLINE=$((SECONDS + MAX))

while (( SECONDS < DEADLINE )); do
    if getent hosts "$PROBE_HOST" >/dev/null 2>&1; then
        exec "$@"
    fi
    sleep 10
done

echo "$(date '+%F %T') [SKIP] sin red tras ${MAX}s — no se ejecuta: $*" >> "$LOG"
exit 75
