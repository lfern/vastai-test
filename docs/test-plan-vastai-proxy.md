# Plan de pruebas: VastAI Proxy

Verificar que el lanzamiento y parada de instancias Vast.ai funciona correctamente
antes de conectar Clawd.

---

## Fase 1 — El container arranca

```bash
docker compose build ollama-proxy
docker compose up ollama-proxy
```

**Qué verificar:**
- Sin errores de build (pip install vastai, fastapi, etc.)
- Los logs muestran las 5 líneas de configuración de arranque
- `curl http://localhost:11434/health` devuelve JSON con `"vastai_status": "stopped"`
- `http://localhost:11434/` carga el panel web en el navegador

---

## Fase 2 — La API key de Vast.ai llega al container

```bash
docker exec -it ollama-proxy vastai show instances
```

**Qué verificar:**
- Responde con una lista (vacía o no) → API key OK
- Error de autenticación → la key no llegó bien al volumen `./vastai-config`

**Si falla:** verificar que `./vastai-config/vast_api_key` existe en el host
y que el volumen está montado:

```bash
docker exec -it ollama-proxy cat /root/.config/vastai/vast_api_key
```

---

## Fase 3 — Búsqueda de ofertas funciona

```bash
docker exec -it ollama-proxy vastai search offers \
  "dph<0.15 reliability>0.999 gpu_name=RTX_3090 num_gpus=1 gpu_ram>=24" \
  -o dph
```

**Qué verificar:**
- Devuelve tabla con ofertas y precios
- Si devuelve vacío → aflojar los filtros (bajar `reliability` a `>0.99`, subir `dph`)

> Si aquí no hay resultados, el lanzamiento fallará.
> Ajustar `SEARCH_QUERY` en `docker-compose.yml` antes de continuar.

---

## Fase 4 — Lanzamiento manual y seguimiento de estado

Abrir **dos terminales en paralelo**.

**Terminal 1** — logs en tiempo real:
```bash
docker compose logs -f ollama-proxy
```

**Terminal 2** — lanzar y hacer polling de estado:
```bash
# Lanzar
curl -s -X POST http://localhost:11434/admin/launch | jq

# Polling cada 15s mientras arranca (~5-10 min)
watch -n 15 "curl -s http://localhost:11434/admin/status | jq '{status,instance_id,ollama_url}'"
```

También se puede seguir el progreso en el panel web `http://localhost:11434/` —
el badge pasa de STOPPED → STARTING → RUNNING.

**Qué verificar en los logs:**
```
[LAUNCH] Buscando ofertas: ...
[LAUNCH] 8 oferta(s). Probando las primeras 5
[LAUNCH] Intento 1/5: oferta 12345678 (RTX_3090, $0.13/h)
[LAUNCH] ✓ Instancia 12345678 creada con oferta ...
[WAIT]   Poll 1/36: status=loading ip=
[WAIT]   Poll 4/36: status=loading ip=1.2.3.4
[WAIT]   Ollama responde (1/3) en http://1.2.3.4:21434
[WAIT]   ✓ Instancia lista en http://1.2.3.4:21434
```

**Posibles fallos y diagnóstico:**

| Log que ves | Causa probable | Acción |
|---|---|---|
| `Oferta X rechazada` en todos los intentos | Oferta ya cogida o error de config | Ver error exacto, ajustar query |
| `Poll N: status=loading` durante >10 min | Imagen tarda en descargar | Esperar, es normal la primera vez |
| `Ollama aún no listo` tras `status=running` | Modelo cargando | Esperar, puede tardar 2-3 min más |
| `Timeout: instancia no arrancó en 12 min` | Demasiado lento | Aumentar `LAUNCH_TIMEOUT_MIN=20` en compose |

---

## Fase 5 — El proxy reenvía peticiones

Una vez `status=running`:

```bash
# Test básico sin streaming
curl -s http://localhost:11434/api/generate \
  -d '{"model":"glm-4.7-flash","prompt":"Di hola en una palabra","stream":false}' | jq

# Test con streaming (debe llegar token a token)
curl -s -N http://localhost:11434/api/generate \
  -d '{"model":"glm-4.7-flash","prompt":"Cuenta del 1 al 5","stream":true}'
```

**Qué verificar:**
- Respuesta coherente del modelo
- En streaming: llegan líneas JSON una a una, no todo de golpe
- Los logs muestran `✓ Completado en Xs — Y bytes`

---

## Fase 6 — Parada manual

```bash
curl -s -X POST http://localhost:11434/admin/stop | jq
# → {"ok": true, "message": "Instancia parada."}

curl -s http://localhost:11434/admin/status | jq '.status'
# → "stopped"
```

Verificar en Vast.ai que la instancia aparece como parada (no destruida):
```bash
docker exec -it ollama-proxy vastai show instances
```

---

## Fase 7 — Auto-parada por inactividad

Para no esperar 15 minutos, bajar temporalmente el timeout en `docker-compose.yml`:

```yaml
- INACTIVITY_MINUTES=2
```

```bash
docker compose up -d --build ollama-proxy

# Lanzar instancia y esperar a que esté running
curl -X POST http://localhost:11434/admin/launch

# Esperar ~3 min sin hacer peticiones y observar en los logs:
# [WATCHER] Inactividad: 2.0 min. Parando instancia...
# [STOP] ✓ Instancia parada

curl http://localhost:11434/admin/status | jq '.status'
# → "stopped"
```

---

## Fase 8 — Streaming de estado durante el lanzamiento

Con la instancia parada, hacer una petición directa y verificar que llegan
los mensajes de progreso mientras arranca:

```bash
curl -s -N http://localhost:11434/api/generate \
  -d '{"model":"glm-4.7-flash","prompt":"Hola","stream":true}'
```

**Debe mostrar:**
```json
{"model":"glm-4.7-flash","message":{"content":"⏳ Arrancando instancia GPU..."},"done":false}
{"model":"glm-4.7-flash","message":{"content":"🔍 Buscando mejor oferta..."},"done":false}
...
{"model":"glm-4.7-flash","message":{"content":"🟢 GPU lista..."},"done":false}
{"model":"glm-4.7-flash","message":{"content":"Hola!"},"done":false}
{"model":"glm-4.7-flash","message":{"content":""},"done":true}
```

---

## Checklist final antes de conectar Clawd

- [ ] Container arranca sin errores
- [ ] API key llega correctamente al container
- [ ] Hay ofertas disponibles con la query configurada
- [ ] Lanzamiento completa en <12 min (ajustar timeout si hace falta)
- [ ] `/api/generate` devuelve respuesta correcta con instancia activa
- [ ] Parada manual funciona
- [ ] Auto-parada por inactividad funciona
- [ ] Panel web muestra el estado correcto en todo momento
