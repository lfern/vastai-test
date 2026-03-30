"""Endpoints compatibles con la API de Ollama (/api/*)."""
import json
import logging
import time
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

import config
from state import state

log = logging.getLogger("ollama")
router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _chat_chunk(content: str, model: str, done: bool = False) -> bytes:
    obj = {
        "model": model, "created_at": _now(),
        "message": {"role": "assistant", "content": content},
        "done": done,
    }
    if done:
        obj["done_reason"] = "stop"
    return (json.dumps(obj) + "\n").encode()

def _gen_chunk(content: str, model: str, done: bool = False) -> bytes:
    return (json.dumps({
        "model": model, "created_at": _now(),
        "response": content, "done": done,
    }) + "\n").encode()


async def _stream(body: dict, endpoint: str) -> AsyncGenerator[bytes, None]:
    model    = body.get("model", config.REMOTE_MODEL)
    chunk_fn = _chat_chunk if endpoint == "chat" else _gen_chunk
    req_id   = f"{endpoint[:3].upper()}-{int(time.time())}"

    log.info(f"[{req_id}] Petición — modelo={model} vastai={state.status}")
    # Extraer mensaje completo para mostrarlo en el panel
    msgs = body.get("messages", [])
    last_user = next((m.get("content","") for m in reversed(msgs) if m.get("role") == "user"), "")
    full_prompt = body.get("prompt", last_user)  # /api/generate usa "prompt"
    preview = (full_prompt[:120] + "…") if len(full_prompt) > 120 else full_prompt
    state.active_requests[req_id] = {
        "model": model, "started_at": time.time(),
        "endpoint": endpoint, "preview": preview,
        "full_prompt": full_prompt,
    }

    # Si la instancia no está corriendo, rechazar con mensaje claro
    if state.status != "running":
        log.warning(f"[{req_id}] Instancia no activa ({state.status}) — lanzamiento manual requerido")
        yield chunk_fn(
            f"⚠️ La instancia GPU no está activa (estado: {state.status}).\n"
            "Lánzala desde el panel de administración: http://localhost:11434/",
            model, done=True,
        )
        return

    # Proxy de la petición real a Vast.ai
    state.last_used = time.time()
    t_start = time.time()
    bytes_proxied = 0
    log.info(f"[{req_id}] Proxying → {state.ollama_url}/api/{endpoint}")

    try:
        async with httpx.AsyncClient(timeout=3600, follow_redirects=True, verify=False) as client:
            async with client.stream(
                "POST",
                f"{state.ollama_url}/api/{endpoint}",
                json=body,
                timeout=httpx.Timeout(connect=10, read=3600, write=60, pool=10),
            ) as resp:
                log.info(f"[{req_id}] HTTP {resp.status_code} de Vast.ai")
                line_buf = b""
                async for chunk in resp.aiter_bytes():
                    state.last_used  = time.time()
                    bytes_proxied   += len(chunk)
                    # Acumular respuesta para el panel
                    line_buf += chunk
                    while b"\n" in line_buf:
                        line, line_buf = line_buf.split(b"\n", 1)
                        try:
                            obj = json.loads(line)
                            token = (obj.get("message") or {}).get("content") \
                                    or obj.get("response") or ""
                            if token and req_id in state.active_requests:
                                state.active_requests[req_id]["response_so_far"] = \
                                    state.active_requests[req_id].get("response_so_far", "") + token
                        except Exception:
                            pass
                    yield chunk

        elapsed = time.time() - t_start
        log.info(f"[{req_id}] ✓ Completado en {elapsed:.1f}s — {bytes_proxied} bytes")

    except httpx.ReadTimeout:
        log.error(f"[{req_id}] Timeout tras {time.time()-t_start:.0f}s")
        yield chunk_fn("\n\n❌ Timeout: la instancia tardó demasiado en responder.", model, done=True)
    except Exception as e:
        log.error(f"[{req_id}] Error: {type(e).__name__}: {e}")
        yield chunk_fn(f"\n\n❌ Error comunicando con la instancia: {e}", model, done=True)
    finally:
        state.active_requests.pop(req_id, None)


@router.post("/api/chat")
async def api_chat(request: Request):
    body = await request.json()
    return StreamingResponse(_stream(body, "chat"), media_type="application/x-ndjson")


@router.post("/api/generate")
async def api_generate(request: Request):
    body = await request.json()
    return StreamingResponse(_stream(body, "generate"), media_type="application/x-ndjson")


@router.get("/api/tags")
async def api_tags():
    if state.status == "running" and state.ollama_url:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{state.ollama_url}/api/tags")
                if r.status_code == 200:
                    return JSONResponse(r.json())
        except Exception as e:
            log.warning(f"[TAGS] No se pudo obtener modelos de la instancia: {e}")
    return JSONResponse({
        "models": [{"name": config.REMOTE_MODEL, "model": config.REMOTE_MODEL,
                    "size": 0, "digest": "", "details": {}}]
    })


@router.get("/api/version")
async def api_version():
    return {"version": "0.5.0"}
