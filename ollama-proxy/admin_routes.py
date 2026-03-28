"""
Endpoints de administración y UI web.

  GET  /              → panel web
  GET  /health        → estado rápido (JSON)
  GET  /admin/status  → estado detallado (JSON)
  POST /admin/launch  → lanzar instancia manualmente
  POST /admin/stop    → parar instancia manualmente
  POST /admin/destroy → destruir instancia (irreversible)
  GET  /admin/instances → todas las instancias en Vast.ai
  GET  /admin/logs    → últimas N líneas de log
"""
import asyncio
import logging
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

import config
import log_buffer
from state import state
from vastai import (
    destroy_managed,
    destroy_instance_sync,
    ensure_running,
    list_instances_sync,
    stop_managed,
)

log = logging.getLogger("admin")
router = APIRouter()


# ---------------------------------------------------------------------------
# Panel web
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_ui():
    with open("/app/static/index.html", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    idle = round((time.time() - state.last_used) / 60, 1) if state.last_used else None
    return {
        "vastai_status":       state.status,
        "instance_id":         state.instance_id,
        "ollama_url":          state.ollama_url,
        "idle_minutes":        idle,
        "stops_after_minutes": config.INACTIVITY_MIN,
    }


@router.get("/admin/status")
async def admin_status():
    idle         = (time.time() - state.last_used) / 60 if state.last_used else None
    stops_in_min = round(config.INACTIVITY_MIN - idle, 1) if idle is not None else None
    return {
        "status":          state.status,
        "instance_id":     state.instance_id,
        "ollama_url":      state.ollama_url,
        "idle_minutes":    round(idle, 1) if idle is not None else None,
        "stops_in_minutes": max(stops_in_min, 0) if stops_in_min is not None else None,
        "config": {
            "remote_model":      config.REMOTE_MODEL,
            "inactivity_min":    config.INACTIVITY_MIN,
            "instance_image":    config.INSTANCE_IMAGE,
            "search_query":      config.SEARCH_QUERY,
            "max_retries":       config.MAX_RETRIES,
            "launch_timeout_min": config.LAUNCH_TIMEOUT,
        },
    }


# ---------------------------------------------------------------------------
# Control manual
# ---------------------------------------------------------------------------

@router.post("/admin/launch")
async def admin_launch():
    """Lanza la instancia manualmente. No bloqueante: devuelve inmediatamente."""
    if state.status in ("running", "starting"):
        return JSONResponse(
            {"ok": False, "message": f"La instancia ya está en estado '{state.status}'"},
            status_code=409,
        )
    log.info("[ADMIN] Lanzamiento manual solicitado")
    asyncio.create_task(ensure_running())
    return {"ok": True, "message": "Lanzamiento iniciado. Consulta /admin/status para ver el progreso."}


@router.post("/admin/stop")
async def admin_stop():
    """Para la instancia gestionada. La instancia queda en Vast.ai pero detenida."""
    if state.status not in ("running", "starting"):
        return JSONResponse(
            {"ok": False, "message": f"No hay instancia activa (estado: '{state.status}')"},
            status_code=409,
        )
    log.info("[ADMIN] Parada manual solicitada")
    ok = await stop_managed()
    return {"ok": ok, "message": "Instancia parada." if ok else "Error al parar la instancia."}


@router.post("/admin/destroy")
async def admin_destroy():
    """Destruye la instancia gestionada. Irreversible: elimina datos y libera el slot."""
    if state.status == "stopped" and state.instance_id is None:
        return JSONResponse(
            {"ok": False, "message": "No hay instancia activa que destruir"},
            status_code=409,
        )
    log.info("[ADMIN] Destrucción manual solicitada")
    ok = await destroy_managed()
    return {"ok": ok, "message": "Instancia destruida." if ok else "Error al destruir la instancia."}


# ---------------------------------------------------------------------------
# Listado de todas las instancias en Vast.ai (incluidas las huérfanas)
# ---------------------------------------------------------------------------

@router.get("/admin/instances")
async def admin_instances():
    """Lista todas las instancias en la cuenta de Vast.ai, no solo la gestionada."""
    try:
        loop      = asyncio.get_event_loop()
        instances = await loop.run_in_executor(None, list_instances_sync)
        return {"ok": True, "instances": instances, "count": len(instances)}
    except Exception as e:
        log.error(f"[ADMIN] Error listando instancias: {e}")
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@router.post("/admin/instances/{instance_id}/destroy")
async def admin_destroy_any(instance_id: int):
    """Destruye cualquier instancia por ID, no solo la gestionada. Útil para huérfanas."""
    log.info(f"[ADMIN] Destrucción de instancia huérfana {instance_id}")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, destroy_instance_sync, instance_id)
        # Si era la gestionada, limpiar estado también
        if state.instance_id == instance_id:
            state.status      = "stopped"
            state.ollama_url  = None
            state.instance_id = None
        return {"ok": True, "message": f"Instancia {instance_id} destruida"}
    except Exception as e:
        log.error(f"[ADMIN] Error destruyendo {instance_id}: {e}")
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@router.get("/admin/logs")
async def admin_logs(n: int = 150):
    """Devuelve las últimas N líneas de log del proxy."""
    return {"logs": log_buffer.get_recent(n)}
