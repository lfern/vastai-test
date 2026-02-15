# Scripts Vast.ai CLI

Scripts para usar el [CLI de Vast.ai](https://cloud.vast.ai/cli/) desde el contenedor (sin instalar Python en el host).

## Requisitos

- Docker y Docker Compose.
- Primera vez: construir la imagen y configurar la API key.

```bash
# Construir imagen (perfil vast)
docker compose --profile vast build

# Configurar API key (obtenerla en https://cloud.vast.ai/cli/)
./set-api-key.sh "tu-api-key"
```

La API key se guarda en `../vastai-config/` (mapeada en el contenedor en `~/.config/vastai/`).

## Scripts (comandos de la pantalla del CLI)

| Script | Descripción |
|--------|-------------|
| `set-api-key.sh "key"` | Login / Set API Key |
| `search-offers.sh [filtros]` | Buscar tipos de instancia |
| `create-instance.sh <id> --image IMG --disk GB ...` | Lanzar instancia |
| `show-instances.sh` | Listar tus instancias |
| `show-instance.sh <id>` | Detalle de una instancia |
| `destroy-instance.sh <id>` | Destruir instancia (irreversible) |
| `ssh-url.sh <id>` | Ver cómo conectar por SSH |
| `execute.sh <id> 'comando'` | Ejecutar comando (ls, rm, du) |
| `start-instance.sh <id>` | Arrancar instancia parada |
| `stop-instance.sh <id>` | Parar instancia |
| `scp-url.sh <id>` | Ayuda para SCP |
| `vastai.sh <subcomando> ...` | Cualquier otro comando del CLI |

## Ejemplos

```bash
# Buscar ofertas (ej. GPUs Ampere, reliability > 0.99)
./search-offers.sh "gpu_ram>=20 num_gpus=1"
./search-offers.sh "reliability>0.99 num_gpus>=4"

# Crear instancia (usa un ID de search-offers)
./create-instance.sh 37744 --image pytorch/pytorch --disk 32 --ssh --direct

# Conectar por SSH (usa la URL que muestra)
./ssh-url.sh 6541241

# Comandos en instancia inactiva
./execute.sh 6541241 'ls -la'
./execute.sh 6541241 'du -d2 -h'
```

## Comando genérico

Para cualquier subcomando del CLI:

```bash
./vastai.sh show user
./vastai.sh search offers "gpu_ram>=24" --raw
```

Documentación completa: [Vast.ai CLI Commands](https://vast.ai/docs/cli/commands).
