"""Tarea de fondo: para la instancia tras N minutos de inactividad."""
import asyncio
import logging
import time

import config
from state import state
from vastai import stop_managed

log = logging.getLogger("watcher")


async def inactivity_watcher():
    log.info(f"[WATCHER] Iniciado. Para instancias tras {config.INACTIVITY_MIN} min de inactividad")
    while True:
        await asyncio.sleep(60)
        if state.status != "running" or state.last_used == 0:
            log.debug(f"[WATCHER] Estado: {state.status} — nada que vigilar")
            continue

        idle_min  = (time.time() - state.last_used) / 60
        remaining = config.INACTIVITY_MIN - idle_min

        if remaining > 0:
            log.debug(f"[WATCHER] Inactividad: {idle_min:.1f} min "
                      f"(para automáticamente en {remaining:.1f} min)")
        else:
            log.info(f"[WATCHER] {idle_min:.1f} min de inactividad alcanzados. Parando instancia...")
            await stop_managed()
