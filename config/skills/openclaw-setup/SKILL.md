# Skill: openclaw-setup

Úsame cuando el usuario necesite conectar el navegador al gateway, aprobar un pairing,
o recuperar el token de acceso.

## Obtener el token

```bash
python3 -c "import json; d=json.load(open('config/openclaw.json')); print(d['gateway']['auth']['token'])"
```

## Ver dispositivos pendientes de pairing

```bash
cat config/devices/pending.json
```

Si el fichero está vacío `{}`, el usuario debe volver a conectar desde el navegador
(introducir URL + token) para que aparezca la solicitud.

## Aprobar pairing pendiente

```bash
python3 - <<'EOF'
import json, time
pending = json.load(open('config/devices/pending.json'))
if not pending:
    print("Sin dispositivos pendientes"); exit()
paired = json.load(open('config/devices/paired.json'))
now = int(time.time() * 1000)
for req_id, req in pending.items():
    did = req['deviceId']
    paired[did] = {**{k: req[k] for k in ('deviceId','publicKey','platform','clientId','clientMode')},
                   'role':'operator','roles':['operator'],'scopes':req['scopes'],
                   'approvedScopes':req['scopes'],'tokens':{},'createdAtMs':now,'approvedAtMs':now}
    print(f"Aprobado: {did}")
json.dump(paired, open('config/devices/paired.json','w'), indent=2)
json.dump({}, open('config/devices/pending.json','w'), indent=2)
EOF
docker compose restart clawd
```

## Flujo completo de primera conexión

1. `docker compose up -d` — levantar servicios
2. Abrir `http://localhost:18789/chat?session=main`
3. Introducir `ws://localhost:18789` + token → Connect
4. Si pide pairing → ejecutar script de aprobación de arriba
5. Reconectar desde el navegador — ya no pedirá pairing

Ver guía completa en `workspace/SETUP.md`.
