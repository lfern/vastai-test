# Guía de instalación desde cero

## Requisitos previos

- Docker + Docker Compose
- Cuenta en [Vast.ai](https://cloud.vast.ai) con saldo
- API key de Vast.ai

---

## 1. Clonar el repositorio

```bash
git clone <repo-url>
cd ollama-test
```

---

## 2. Configurar credenciales

Copia el fichero de ejemplo y edítalo:

```bash
cp .env.example .env
```

Edita `.env` y rellena al menos:

```env
VAST_API_KEY=<tu api key de cloud.vast.ai/account>
REMOTE_MODEL=glm-4.7-flash          # modelo a cargar en la instancia GPU
SEARCH_QUERY=dph<0.15 reliability>0.999 gpu_name=RTX_3090 num_gpus=1 gpu_ram>=24 cpu_ram>=32 disk_space>=32
INSTANCE_IMAGE=vastai/ollama:0.15.4
INSTANCE_DISK_GB=32
LAUNCH_MAX_RETRIES=5
LAUNCH_TIMEOUT_MIN=8
POLL_INTERVAL_SEC=15
```

---

## 3. Configurar OpenClaw

```bash
cp config/openclaw.example.json config/openclaw.json
```

El token de acceso al gateway lo genera OpenClaw automáticamente en el primer arranque
y lo escribe en `config/openclaw.json`. No hace falta editarlo manualmente.

---

## 4. Levantar los servicios

```bash
docker compose up -d
```

Esto arranca:
- **ollama-proxy** en `http://localhost:11434` — panel admin en esa misma URL
- **clawd** (OpenClaw) en `http://localhost:18789`

---

## 5. Conectar el navegador a OpenClaw

### 5a. Obtener el token

Espera ~10 segundos a que OpenClaw arranque y lea el token que generó:

```bash
python3 -c "import json; d=json.load(open('config/openclaw.json')); print(d['gateway']['auth']['token'])"
```

### 5b. Conectar

1. Abrir `http://localhost:18789/chat?session=main`
2. En el formulario introducir:
   - **WebSocket URL**: `ws://localhost:18789`
   - **Token**: *(el del paso anterior)*
3. Clic en **Connect**

### 5c. Aprobar el pairing (primera vez)

El navegador pedirá pairing. Ejecuta desde el directorio del proyecto:

```bash
python3 - <<'EOF'
import json, time

pending = json.load(open('config/devices/pending.json'))
if not pending:
    print("Sin dispositivos pendientes — vuelve a conectar desde el navegador primero")
    exit()

paired = json.load(open('config/devices/paired.json'))
now = int(time.time() * 1000)

for req_id, req in pending.items():
    did = req['deviceId']
    paired[did] = {
        'deviceId': did, 'publicKey': req['publicKey'],
        'platform': req['platform'], 'clientId': req['clientId'],
        'clientMode': req['clientMode'], 'role': 'operator',
        'roles': ['operator'], 'scopes': req['scopes'],
        'approvedScopes': req['scopes'], 'tokens': {},
        'createdAtMs': now, 'approvedAtMs': now,
    }
    print(f"Aprobado: {did} ({req['platform']})")

json.dump(paired, open('config/devices/paired.json', 'w'), indent=2)
json.dump({},     open('config/devices/pending.json', 'w'), indent=2)
EOF

docker compose restart clawd
```

Luego reconecta el navegador — ya no pedirá pairing.

> El pairing queda guardado en `config/devices/paired.json` y sobrevive a reinicios.
> Solo hay que repetirlo si usas un navegador nuevo o borras ese fichero.

---

## 6. Lanzar una instancia GPU en Vast.ai

1. Abre el panel admin: `http://localhost:11434/`
2. Pulsa **Lanzar instancia**
3. El proxy buscará ofertas que cumplan el `SEARCH_QUERY` del `.env` y lanzará la mejor
4. El proceso tarda ~5-10 min (descarga del modelo incluida)
5. Cuando el estado cambie a **running**, el proxy ya puede recibir peticiones

> Tras un reinicio del proxy, si hay una instancia running en Vast.ai,
> se conecta automáticamente sin intervención manual.

---

## 7. Probar el stack completo

```bash
# El proxy responde con el modelo grande
curl -s -X POST http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-4.7-flash","messages":[{"role":"user","content":"Hola"}],"stream":false}' \
  | python3 -m json.tool | grep content

# OpenClaw también funciona desde su CLI
docker exec clawd node openclaw.mjs agent \
  --message "Cuánto es 2+2?" --session-id test --json \
  | python3 -m json.tool | grep text
```

---

## 8. Parar / destruir la instancia

Desde el panel `http://localhost:11434/`:
- **Parar** — detiene la instancia pero la conserva (se puede reiniciar, sigue costando algo)
- **Destruir** — elimina la instancia definitivamente (deja de cobrar)

---

## Estructura del proyecto

```
.
├── .env                        # credenciales (no en git)
├── .env.example                # plantilla de credenciales
├── docker-compose.yml          # servicios: ollama-proxy + clawd
├── ollama-proxy/               # proxy Ollama-compatible + panel admin
│   ├── Dockerfile
│   ├── entrypoint.sh           # escribe VAST_API_KEY al arrancar
│   ├── main.py                 # FastAPI app + auto-attach al inicio
│   ├── admin_routes.py         # endpoints /admin/*
│   ├── ollama_routes.py        # endpoints /api/*
│   ├── vastai.py               # gestión ciclo de vida Vast.ai
│   ├── config.py               # variables de entorno
│   ├── state.py                # estado compartido
│   └── static/index.html       # panel web
├── config/
│   ├── openclaw.example.json   # plantilla de config OpenClaw (en git)
│   ├── openclaw.json           # config real con token (NO en git)
│   ├── skills/                 # skills del agente (en git)
│   │   └── openclaw-setup/SKILL.md
│   ├── devices/                # pairing de dispositivos (NO en git)
│   ├── agents/                 # historial de sesiones (NO en git)
│   └── workspace/              # workspace del agente (NO en git)
├── vastai-scripts/             # scripts CLI de Vast.ai para uso manual
└── docs/                       # documentación adicional
```

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `FileExistsError: /root/.config/vastai` | `VAST_API_KEY` no en `.env` | Verificar `.env` y hacer `docker compose up -d ollama-proxy` |
| Panel admin muestra `stopped` tras reinicio | Auto-attach tardó | Esperar 15s o recargar |
| OpenClaw pide pairing | Navegador nuevo o estado borrado | Ejecutar script del paso 5c |
| OpenClaw pide token | No se introdujo en la UI | Repetir paso 5b |
| Instancia no arranca (timeout) | Oferta ocupada o lenta | Pulsar Lanzar de nuevo (prueba otra oferta) |
| `dph<0.15` sin resultados | No hay GPUs baratas disponibles | Subir el límite de precio en `SEARCH_QUERY` |
