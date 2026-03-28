"""
Operaciones con el CLI de Vast.ai y gestión del ciclo de vida de la instancia.
Las funciones _sync son bloqueantes y se ejecutan en un thread via run_in_executor.
"""
import asyncio
import json
import logging
import subprocess
import time
import httpx

import config
from state import state

log = logging.getLogger("vastai")


# ---------------------------------------------------------------------------
# Helpers CLI
# ---------------------------------------------------------------------------

def _cli(*args: str) -> tuple[int, str, str]:
    cmd = ["vastai"] + list(args)
    log.debug(f"[CLI] {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.warning(f"[CLI] código {r.returncode}: {r.stderr.strip()[:300]}")
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _parse_json(text: str):
    """Parsea JSON aunque la salida del CLI lleve texto previo (ej: 'Started. {...}')."""
    text = text.strip()
    if text.startswith(("{", "[")):
        return json.loads(text)
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith(("{", "[")):
            try:
                return json.loads(
                    line.replace("'", '"')
                        .replace("True", "true")
                        .replace("False", "false")
                        .replace("None", "null")
                )
            except Exception:
                pass
    raise ValueError(f"No se encontró JSON en: {text!r}")


# ---------------------------------------------------------------------------
# Operaciones individuales (síncronas)
# ---------------------------------------------------------------------------

def list_instances_sync() -> list:
    rc, out, err = _cli("show", "instances", "--raw")
    if rc != 0:
        raise RuntimeError(f"Error listando instancias: {err}")
    if not out or out in ("null", "[]", ""):
        return []
    return json.loads(out)


def get_instance_sync(instance_id: int) -> dict:
    rc, out, err = _cli("show", "instance", str(instance_id), "--raw")
    if rc != 0:
        raise RuntimeError(f"Instancia {instance_id} no encontrada: {err}")
    return json.loads(out)


def stop_instance_sync(instance_id: int):
    log.info(f"[STOP] Parando instancia {instance_id}")
    rc, out, err = _cli("stop", "instance", str(instance_id))
    if rc != 0:
        raise RuntimeError(f"Error parando instancia: {err}")
    log.info(f"[STOP] ✓ Instancia {instance_id} parada")


def destroy_instance_sync(instance_id: int):
    log.info(f"[DESTROY] Destruyendo instancia {instance_id}")
    rc, out, err = _cli("destroy", "instance", str(instance_id))
    if rc != 0:
        raise RuntimeError(f"Error destruyendo instancia: {err}")
    log.info(f"[DESTROY] ✓ Instancia {instance_id} destruida")


# ---------------------------------------------------------------------------
# Lanzamiento completo (síncrono, bloqueante ~5-12 min)
# ---------------------------------------------------------------------------

def _launch_sync() -> bool:
    """Busca oferta → crea instancia → espera arranque → verifica Ollama."""

    # 1. Buscar ofertas
    log.info(f"[LAUNCH] Buscando ofertas: {config.SEARCH_QUERY}")
    rc, out, err = _cli("search", "offers", config.SEARCH_QUERY, "--raw", "-o", "dph")
    if rc != 0:
        log.error(f"[LAUNCH] Error buscando ofertas: {err}")
        return False
    try:
        offers = json.loads(out)
    except Exception as e:
        log.error(f"[LAUNCH] Error parseando ofertas: {e} — {out[:200]}")
        return False
    if not offers:
        log.error("[LAUNCH] No hay ofertas para la query configurada")
        return False

    log.info(f"[LAUNCH] {len(offers)} oferta(s). Probando las primeras {config.MAX_RETRIES}")
    offers = offers[:config.MAX_RETRIES]

    env_str = (
        f"-p {config.OLLAMA_HOST_PORT}:{config.OLLAMA_HOST_PORT} "
        f"-e OLLAMA_MODEL={config.REMOTE_MODEL} "
        f'-e PORTAL_CONFIG="localhost:1111:11111:/:Instance Portal|'
        f"localhost:{config.OLLAMA_HOST_PORT}:{config.OLLAMA_CONTAINER_PORT}:/:Ollama API\" "
        f"-e OPEN_BUTTON_PORT=1111 -e OPEN_BUTTON_TOKEN=1 "
        f"-e JUPYTER_DIR=/ -e DATA_DIRECTORY=/workspace/"
    )

    # 2. Intentar crear instancia con cada oferta hasta que una funcione
    instance_id = None
    for i, offer in enumerate(offers):
        offer_id  = str(offer["id"])
        offer_dph = offer.get("dph_total", "?")
        offer_gpu = offer.get("gpu_name", "?")
        log.info(f"[LAUNCH] Intento {i+1}/{len(offers)}: "
                 f"oferta {offer_id} ({offer_gpu}, ${offer_dph}/h)")

        rc, out, err = _cli(
            "create", "instance", offer_id,
            "--image", config.INSTANCE_IMAGE,
            "--env", env_str,
            "--onstart-cmd", "entrypoint.sh",
            "--disk", str(config.INSTANCE_DISK),
            "--raw",
        )
        if rc == 0 and out:
            try:
                data = _parse_json(out)
                iid  = data.get("new_contract")
                if iid:
                    instance_id = int(iid)
                    state.instance_id = instance_id
                    log.info(f"[LAUNCH] ✓ Instancia {instance_id} creada con oferta {offer_id}")
                    break
                log.warning(f"[LAUNCH] Sin new_contract en respuesta: {data}")
            except Exception as e:
                log.warning(f"[LAUNCH] Error parseando create: {e} — {out[:200]}")
        else:
            log.warning(f"[LAUNCH] Oferta {offer_id} rechazada: {(err or out)[:200]}")

    if instance_id is None:
        log.error("[LAUNCH] Todos los intentos fallaron")
        return False

    # 3. Polling hasta que Ollama responda
    max_polls   = (config.LAUNCH_TIMEOUT * 60) // config.POLL_INTERVAL
    ollama_hits = 0
    for attempt in range(1, max_polls + 1):
        time.sleep(config.POLL_INTERVAL)
        try:
            data   = get_instance_sync(instance_id)
            status = data.get("actual_status", "unknown")
            ip     = data.get("public_ipaddr", "")
            log.info(f"[WAIT] Poll {attempt}/{max_polls}: status={status} ip={ip}")
        except Exception as e:
            log.warning(f"[WAIT] Poll {attempt}: {e}")
            continue

        if status in ("error", "exited", "failed"):
            log.error(f"[WAIT] Instancia entró en error: {status}")
            return False

        if status == "running" and ip:
            url = f"http://{ip}:{config.OLLAMA_HOST_PORT}"
            try:
                r = httpx.get(f"{url}/api/tags", timeout=5)
                if r.status_code == 200:
                    ollama_hits += 1
                    log.info(f"[WAIT] Ollama responde ({ollama_hits}/3) en {url}")
                    if ollama_hits >= 3:
                        state.ollama_url = url
                        log.info(f"[WAIT] ✓ Instancia {instance_id} lista en {url}")
                        return True
                else:
                    ollama_hits = 0
            except Exception as e:
                log.debug(f"[WAIT] Ollama aún no listo: {e}")
                ollama_hits = 0

    log.error(f"[WAIT] Timeout: instancia no arrancó en {config.LAUNCH_TIMEOUT} min")
    return False


# ---------------------------------------------------------------------------
# Gestión asíncrona del estado
# ---------------------------------------------------------------------------

async def ensure_running() -> tuple[bool, bool]:
    """
    Garantiza que la instancia está corriendo.
    Devuelve (éxito, fue_necesario_lanzar).
    Solo un coroutine ejecuta el lanzamiento; los demás esperan.
    """
    if state.status == "running":
        return True, False

    if state.status == "starting":
        log.info("[LAUNCH] Ya arrancando en otro request, esperando...")
        await state._ready_event.wait()
        return state.status == "running", False

    async with state._launch_lock:
        if state.status == "running":
            return True, False
        if state.status != "starting":
            state.status = "starting"
            state._ready_event.clear()

    loop    = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, _launch_sync)

    state.status = "running" if success else "stopped"
    state._ready_event.set()

    if not success:
        log.error("[LAUNCH] Lanzamiento fallido — comprueba API key y ofertas disponibles")
    return success, True


async def stop_managed() -> bool:
    """Para la instancia gestionada y actualiza el estado."""
    if not state.instance_id:
        log.warning("[STOP] No hay instancia activa que parar")
        return False
    iid = state.instance_id
    state.status = "stopping"
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, stop_instance_sync, iid)
    except Exception as e:
        log.error(f"[STOP] Error: {e}")
        state.status = "stopped"
        state.ollama_url  = None
        state.instance_id = None
        return False
    state.status      = "stopped"
    state.ollama_url  = None
    state.instance_id = None
    return True


async def destroy_managed() -> bool:
    """Destruye la instancia gestionada (irreversible)."""
    if not state.instance_id:
        log.warning("[DESTROY] No hay instancia activa que destruir")
        return False
    iid = state.instance_id
    state.status = "stopping"
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, destroy_instance_sync, iid)
    except Exception as e:
        log.error(f"[DESTROY] Error: {e}")
        state.status = "stopped"
        state.ollama_url  = None
        state.instance_id = None
        return False
    state.status      = "stopped"
    state.ollama_url  = None
    state.instance_id = None
    return True
