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

# Patrones en los logs de la instancia que indican fallo irrecuperable
_FATAL_LOG_PATTERNS = [
    "oom",
    "out of memory",
    "killed",
    "failed to create",
    "cannot allocate",
    "exec format error",
]


_ANSI_ESCAPE = __import__('re').compile(r'\x1b\[[0-9;?]*[A-Za-z]|\x1b\[\d*[A-Za-z]|\r')


def _check_instance_logs(instance_id: int) -> tuple[bool, str]:
    """
    Comprueba los logs de la instancia buscando errores fatales.
    vastai logs devuelve texto plano con:
      - líneas "waiting on logs..." mientras S3 no tiene contenido
      - códigos de escape ANSI (progress bars de ollama pull)
    Filtra ambas cosas antes de escanear.
    Devuelve (fatal_error_found, descripción).
    """
    rc, out, err = _cli("logs", str(instance_id), "--tail", "100")
    if rc != 0 or not out:
        return False, ""

    # Strip ANSI escapes y filtrar líneas de espera
    real_lines = []
    for line in out.splitlines():
        if "waiting on logs" in line.lower():
            continue
        clean = _ANSI_ESCAPE.sub("", line).strip()
        if clean:
            real_lines.append(clean)

    if not real_lines:
        return False, ""   # aún no hay logs reales

    content = "\n".join(real_lines)
    log.debug(f"[LOGS] Instancia {instance_id} — últimas líneas limpias: {content[-400:]!r}")

    lower = content.lower()
    for pattern in _FATAL_LOG_PATTERNS:
        if pattern in lower:
            for line in real_lines:
                if pattern in line.lower():
                    return True, line.strip()
    return False, ""


def _destroy_quietly(instance_id: int):
    """Destruye una instancia sin lanzar excepciones (para cleanup en errores)."""
    try:
        destroy_instance_sync(instance_id)
    except Exception as e:
        log.warning(f"[LAUNCH] No se pudo destruir instancia {instance_id}: {e}")


def _wait_for_instance(instance_id: int, offer_label: str) -> bool:
    """
    Espera a que una instancia esté lista y Ollama responda.
    Comprueba logs buscando errores fatales para abortar antes del timeout.
    Devuelve True si la instancia arrancó correctamente.
    """
    max_polls   = (config.LAUNCH_TIMEOUT * 60) // config.POLL_INTERVAL
    ollama_hits = 0

    for attempt in range(1, max_polls + 1):
        time.sleep(config.POLL_INTERVAL)

        # Estado de la instancia
        try:
            data   = get_instance_sync(instance_id)
            status = data.get("actual_status", "unknown")
            ip     = data.get("public_ipaddr", "")
            log.info(f"[WAIT] {offer_label} poll {attempt}/{max_polls}: status={status} ip={ip or '-'}")
        except Exception as e:
            log.warning(f"[WAIT] {offer_label} poll {attempt}: no se pudo obtener estado: {e}")
            continue

        # Error de estado reportado por Vast.ai
        if status in ("error", "exited", "failed"):
            log.error(f"[WAIT] {offer_label} entró en estado de error: {status}")
            return False

        # Comprobar logs en cada poll buscando errores fatales del contenedor
        fatal, msg = _check_instance_logs(instance_id)
        if fatal:
            log.error(f"[WAIT] {offer_label} error fatal en logs: {msg}")
            return False

        # Instancia running con IP → verificar Ollama
        if status == "running" and ip:
            url = f"http://{ip}:{config.OLLAMA_HOST_PORT}"
            try:
                r = httpx.get(f"{url}/api/tags", timeout=5)
                if r.status_code == 200:
                    ollama_hits += 1
                    log.info(f"[WAIT] {offer_label} Ollama responde ({ollama_hits}/3) en {url}")
                    if ollama_hits >= 3:
                        state.ollama_url = url
                        log.info(f"[WAIT] ✓ {offer_label} lista en {url}")
                        return True
                else:
                    ollama_hits = 0
            except Exception as e:
                log.debug(f"[WAIT] {offer_label} Ollama aún no listo: {e}")
                ollama_hits = 0

    log.error(f"[WAIT] {offer_label} timeout tras {config.LAUNCH_TIMEOUT} min")
    return False


def _launch_sync() -> bool:
    """
    Busca ofertas y para cada una: crea instancia → espera → comprueba logs.
    Si una instancia falla (error en logs, timeout o error de estado),
    la destruye y prueba la siguiente oferta.
    """

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

    # 2. Para cada oferta: crear instancia → esperar → si falla, destruir y probar la siguiente
    for i, offer in enumerate(offers):
        offer_id   = str(offer["id"])
        offer_dph  = offer.get("dph_total", "?")
        offer_gpu  = offer.get("gpu_name", "?")
        offer_label = f"oferta {offer_id} ({offer_gpu}, ${offer_dph}/h)"
        log.info(f"[LAUNCH] Intento {i+1}/{len(offers)}: {offer_label}")

        # Crear instancia
        rc, out, err = _cli(
            "create", "instance", offer_id,
            "--image", config.INSTANCE_IMAGE,
            "--env", env_str,
            "--onstart-cmd", "entrypoint.sh",
            "--disk", str(config.INSTANCE_DISK),
            "--raw",
        )
        if rc != 0 or not out:
            log.warning(f"[LAUNCH] {offer_label} rechazada al crear: {(err or out)[:200]}")
            continue

        try:
            data        = _parse_json(out)
            instance_id = data.get("new_contract")
            if not instance_id:
                log.warning(f"[LAUNCH] {offer_label} sin new_contract: {data}")
                continue
            instance_id = int(instance_id)
        except Exception as e:
            log.warning(f"[LAUNCH] {offer_label} error parseando create: {e} — {out[:200]}")
            continue

        state.instance_id = instance_id
        log.info(f"[LAUNCH] ✓ Instancia {instance_id} creada. Esperando arranque...")

        # Esperar arranque con comprobación de logs
        ok = _wait_for_instance(instance_id, offer_label)
        if ok:
            return True

        # Falló → destruir y probar siguiente oferta
        log.warning(f"[LAUNCH] {offer_label} falló. Destruyendo y probando siguiente...")
        _destroy_quietly(instance_id)
        state.instance_id = None
        state.ollama_url  = None

    log.error("[LAUNCH] Todas las ofertas fallaron")
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
