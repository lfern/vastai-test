"""
Endpoints de administración y UI web.

  GET  /              → panel web
  GET  /health        → estado rápido (JSON)
  GET  /admin/status  → estado detallado (JSON)
  POST /admin/launch         → lanzar instancia manualmente
  POST /admin/stop           → parar instancia manualmente
  POST /admin/destroy        → destruir instancia (irreversible)
  POST /admin/restart-ollama → reiniciar proceso Ollama en la instancia (sin perder modelo)
  GET  /admin/instances      → todas las instancias en Vast.ai
  GET  /admin/logs           → últimas N líneas de log
"""
import asyncio
import logging
import time
from fastapi import APIRouter, Query
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
    now          = time.time()
    idle         = (now - state.last_used) / 60 if state.last_used else None
    stops_in_min = round(config.INACTIVITY_MIN - idle, 1) if idle is not None else None
    active = [
        {"req_id": k, "model": v["model"], "endpoint": v["endpoint"],
         "elapsed_sec": round(now - v["started_at"], 1),
         "preview": v.get("preview", ""),
         "full_prompt": v.get("full_prompt", ""),
         "response_so_far": v.get("response_so_far", "")}
        for k, v in state.active_requests.items()
    ]
    return {
        "status":           state.status,
        "instance_id":      state.instance_id,
        "ollama_url":       state.ollama_url,
        "idle_minutes":     round(idle, 1) if idle is not None else None,
        "stops_in_minutes": max(stops_in_min, 0) if stops_in_min is not None else None,
        "active_requests":  active,
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

@router.post("/admin/restart-ollama")
async def admin_restart_ollama():
    """Reinicia el proceso Ollama en la instancia remota sin perder el modelo descargado."""
    if not state.instance_id:
        return JSONResponse({"ok": False, "message": "No hay instancia activa"}, status_code=409)

    def _restart():
        from vastai import _cli
        # Intentar systemctl primero, luego pkill como fallback
        rc, out, err = _cli("execute", str(state.instance_id),
                            "pkill -f 'ollama serve' || true")
        return rc, out or err

    try:
        loop = asyncio.get_event_loop()
        rc, msg = await loop.run_in_executor(None, _restart)
        log.info(f"[ADMIN] Ollama reiniciado en instancia {state.instance_id}: {msg}")
        # Marcar como stopped para forzar re-verificación en la próxima petición
        state.ollama_url = None
        state.status = "stopped"
        return {"ok": True, "message": "Ollama reiniciado. El proxy se reconectará automáticamente al arrancar."}
    except Exception as e:
        log.error(f"[ADMIN] Error reiniciando Ollama: {e}")
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@router.get("/admin/billing")
async def admin_billing():
    """Crédito disponible y gasto total de la cuenta Vast.ai."""
    def _fetch():
        from vastai import _cli
        rc, out, err = _cli("show", "user", "--raw")
        if rc != 0:
            raise RuntimeError(err)
        import json
        d = json.loads(out)
        return {
            "credit":      round(d.get("credit", 0), 4),
            "total_spend": round(abs(d.get("total_spend", 0)), 4),
            "balance":     round(d.get("balance", 0), 4),
        }
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _fetch)
        return {"ok": True, **data}
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@router.post("/admin/attach")
async def admin_attach(instance_id: int = Query(...), ollama_url: str = Query(...)):
    """Registra una instancia ya en marcha en el estado del proxy (sin relanzar)."""
    state.instance_id = instance_id
    state.ollama_url  = ollama_url
    state.status      = "running"
    log.info(f"[ADMIN] Instancia {instance_id} registrada manualmente en {ollama_url}")
    return {"ok": True, "message": f"Instancia {instance_id} registrada en {ollama_url}"}


@router.get("/admin/logs")
async def admin_logs(n: int = 150):
    """Devuelve las últimas N líneas de log del proxy."""
    return {"logs": log_buffer.get_recent(n)}


# ---------------------------------------------------------------------------
# Logs de instancia Vast.ai (proxy hacia la API de cloud.vast.ai)
# ---------------------------------------------------------------------------


def _fetch_logs_via_cli(instance_id: int, daemon: bool) -> str:
    import re, subprocess
    args = ["vastai", "logs", str(instance_id), "--tail", "500"]
    if daemon:
        args += ["--daemon-logs"]
    r   = subprocess.run(args, capture_output=True, text=True, timeout=30)
    raw = r.stdout or r.stderr or ""
    ansi = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')
    lines = [
        ansi.sub("", line).strip()
        for line in raw.splitlines()
        if "waiting on logs" not in line.lower() and ansi.sub("", line).strip()
    ]
    return "\n".join(lines)


@router.get("/admin/instance-logs")
async def admin_instance_logs(
    instance_id: int  = Query(...),
    daemon:      bool = Query(False),
):
    """Obtiene logs de instancia via CLI (un tipo a la vez para evitar colisión S3)."""
    try:
        loop    = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, _fetch_logs_via_cli, instance_id, daemon)
        return JSONResponse({"ok": True, "content": content})
    except Exception as e:
        log.error(f"[ADMIN] Error obteniendo logs de instancia {instance_id}: {e}")
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)
