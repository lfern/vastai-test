"""Punto de entrada: crea la app FastAPI y registra routers."""
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


@app.on_event("startup")
async def on_startup():
    log.info("── Ollama Proxy arrancado ────────────────────────────────")
    log.info(f"  Modelo remoto : {config.REMOTE_MODEL}")
    log.info(f"  Imagen        : {config.INSTANCE_IMAGE}")
    log.info(f"  Query GPU     : {config.SEARCH_QUERY}")
    log.info(f"  Panel web     : http://localhost:11434/")
    log.info("─────────────────────────────────────────────────────────")
