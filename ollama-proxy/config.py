"""Configuración via variables de entorno (definidas en docker-compose.yml)."""
import os

INACTIVITY_MIN   = int(os.getenv("INACTIVITY_MINUTES", "15"))
REMOTE_MODEL     = os.getenv("REMOTE_MODEL", "glm-4.7-flash")
SEARCH_QUERY     = os.getenv("SEARCH_QUERY",
                              "dph<0.15 reliability>0.999 gpu_name=RTX_3090 "
                              "num_gpus=1 gpu_ram>=24 cpu_ram>=32 disk_space>=32")
INSTANCE_IMAGE   = os.getenv("INSTANCE_IMAGE", "vastai/ollama:0.15.4")
INSTANCE_DISK    = int(os.getenv("INSTANCE_DISK_GB", "32"))
MAX_RETRIES      = int(os.getenv("LAUNCH_MAX_RETRIES", "5"))
STATUS_INTERVAL  = float(os.getenv("STATUS_INTERVAL_SEC", "8"))
POLL_INTERVAL    = int(os.getenv("POLL_INTERVAL_SEC", "20"))
LAUNCH_TIMEOUT   = int(os.getenv("LAUNCH_TIMEOUT_MIN", "12"))

OLLAMA_HOST_PORT      = 21434   # puerto expuesto en la instancia remota
OLLAMA_CONTAINER_PORT = 11434   # puerto interno de Ollama en la instancia
