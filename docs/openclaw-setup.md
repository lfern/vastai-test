# OpenClaw Setup — Guía de conexión

## Arquitectura

```
Navegador
  └─► OpenClaw UI  (http://localhost:18789/chat?session=main)
        └─► Gateway WebSocket  (ws://localhost:18789)
              └─► ollama-proxy  (http://ollama-proxy:11434)
                    └─► Vast.ai instancia GPU remota
```

---

## 1. Token de acceso

El token está en `config/openclaw.json` bajo `gateway.auth.token`.

**Leerlo:**
```bash
python3 -c "import json; d=json.load(open('config/openclaw.json')); print(d['gateway']['auth']['token'])"
```

Si no existe todavía (primer arranque), OpenClaw lo genera automáticamente al iniciar el gateway.
Después de que lo genere, aparece en `config/openclaw.json`.

---

## 2. Conectar el navegador

1. Abrir: `http://localhost:18789/chat?session=main`
2. Introducir en el formulario:
   - **WebSocket URL**: `ws://localhost:18789`
   - **Token**: *(el del paso anterior)*
3. Hacer clic en Connect

---

## 3. Pairing de dispositivo (primera vez por navegador)

Después de introducir el token, el navegador pedirá **pairing**.
El gateway requiere que cada dispositivo nuevo sea aprobado explícitamente.

### Opción A — Aprobación automática via script

```bash
# Desde el directorio del proyecto
python3 - <<'EOF'
import json, time

pending = json.load(open('config/devices/pending.json'))
if not pending:
    print("No hay dispositivos pendientes")
    exit()

paired = json.load(open('config/devices/paired.json'))
now = int(time.time() * 1000)

for req_id, req in pending.items():
    device_id = req['deviceId']
    paired[device_id] = {
        'deviceId':       device_id,
        'publicKey':      req['publicKey'],
        'platform':       req['platform'],
        'clientId':       req['clientId'],
        'clientMode':     req['clientMode'],
        'role':           'operator',
        'roles':          ['operator'],
        'scopes':         req['scopes'],
        'approvedScopes': req['scopes'],
        'tokens':         {},
        'createdAtMs':    now,
        'approvedAtMs':   now,
    }
    print(f"Aprobado: {device_id} ({req['platform']} / {req['clientId']})")

json.dump(paired, open('config/devices/paired.json', 'w'), indent=2)
json.dump({},     open('config/devices/pending.json', 'w'), indent=2)
EOF

# Reiniciar el gateway para que recargue los dispositivos
docker compose restart clawd
```

### Opción B — Manual

1. Abrir `config/devices/pending.json` — verás el dispositivo esperando aprobación
2. Copiar la entrada al fichero `config/devices/paired.json` con este formato:
   ```json
   {
     "<deviceId>": {
       "deviceId": "<deviceId>",
       "publicKey": "<del pending>",
       "platform": "<del pending>",
       "clientId": "<del pending>",
       "clientMode": "<del pending>",
       "role": "operator",
       "roles": ["operator"],
       "scopes": ["operator.admin","operator.read","operator.write","operator.approvals","operator.pairing"],
       "approvedScopes": ["operator.admin","operator.read","operator.write","operator.approvals","operator.pairing"],
       "tokens": {},
       "createdAtMs": <timestamp ms>,
       "approvedAtMs": <timestamp ms>
     }
   }
   ```
3. Vaciar `config/devices/pending.json` → `{}`
4. `docker compose restart clawd`

---

## 4. El pairing persiste

Una vez aprobado, el dispositivo queda en `config/devices/paired.json`.
Como ese fichero está en el volumen `./config`, **sobrevive a reinicios y recreaciones del container**.
No hace falta volver a hacer pairing a menos que se borre ese fichero o se use un navegador nuevo.

---

## 5. Panel de administración Vast.ai

- **URL**: `http://localhost:11434/`
- **Lanzar instancia**: botón "Lanzar" en el panel
- **Estado**: el proxy detecta automáticamente instancias running al arrancar

---

## Troubleshooting

| Problema | Causa | Solución |
|---|---|---|
| `pairing required` | Navegador nuevo o fichero borrado | Ejecutar script del paso 3 |
| `token_missing` | No se introdujo el token en la UI | Introducirlo en el formulario de conexión |
| `FileExistsError: /root/.config/vastai` | VAST_API_KEY no en .env | Verificar que `.env` tiene `VAST_API_KEY=...` |
| Proxy sin instancia tras reinicio | Auto-attach tardó o falló | Esperar 10s o usar `/admin/attach` |
