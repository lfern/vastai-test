"""Punto de entrada: crea la app FastAPI y registra routers."""
import asyncio
import logging

import log_buffer
import config
from admin_routes import router as admin_router
from ollama_routes import router as ollama_router

# Configurar logging antes de que ningún módulo cree un logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log_buffer.setup()   # añade el handler de buffer en memoria

from fastapi import FastAPI  # noqa: E402 (import después de logging)

log = logging.getLogger("main")

app = FastAPI(title="Ollama Proxy / VastAI Lifecycle Manager", docs_url="/api/docs")
app.include_router(ollama_router)
app.include_router(admin_router)


async def _auto_attach():
    """
    Al arrancar, busca instancias en running en Vast.ai y se conecta automáticamente
    a la primera que tenga Ollama respondiendo. Evita tener que usar /admin/attach
    manualmente tras un reinicio del proxy.
    """
    import httpx
    from vastai import list_instances_sync, get_instance_sync
    from state import state

    try:
        loop = asyncio.get_event_loop()
        instances = await loop.run_in_executor(None, list_instances_sync)
    except Exception as e:
        log.warning(f"[STARTUP] No se pudo listar instancias Vast.ai: {e}")
        return

    running = [i for i in instances if i.get("actual_status") == "running"]
    if not running:
        log.info("[STARTUP] No hay instancias running en Vast.ai")
        return

    log.info(f"[STARTUP] {len(running)} instancia(s) running — buscando Ollama accesible...")
    for inst in running:
        iid  = inst["id"]
        ip   = inst.get("public_ipaddr", "")
        ports = inst.get("ports", {}) or {}
        port_key = f"{config.OLLAMA_CONTAINER_PORT}/tcp"
        mappings = ports.get(port_key, [])
        ext_port = mappings[0]["HostPort"] if mappings else config.OLLAMA_CONTAINER_PORT
        url = f"http://{ip}:{ext_port}"
        try:
            async with httpx.AsyncClient(timeout=5, verify=False) as client:
                r = await client.get(f"{url}/api/tags")
            if r.status_code == 200:
                state.instance_id = iid
                state.ollama_url  = url
                state.status      = "running"
                log.info(f"[STARTUP] ✓ Auto-attach: instancia {iid} en {url}")
                return
        except Exception:
            log.debug(f"[STARTUP] Instancia {iid} ({url}) no responde aún")

    log.info("[STARTUP] Ninguna instancia running responde en Ollama todavía")


@app.on_event("startup")
async def on_startup():
    log.info("── Ollama Proxy arrancado ────────────────────────────────")
    log.info(f"  Modelo remoto : {config.REMOTE_MODEL}")
    log.info(f"  Imagen        : {config.INSTANCE_IMAGE}")
    log.info(f"  Query GPU     : {config.SEARCH_QUERY}")
    log.info(f"  Panel web     : http://localhost:11434/")
    log.info("─────────────────────────────────────────────────────────")
    asyncio.create_task(_auto_attach())
