"""Estado compartido de la instancia Vast.ai."""
import asyncio
from typing import Optional


class VastaiState:
    def __init__(self):
        self.status: str = "stopped"       # stopped | starting | running | stopping
        self.ollama_url: Optional[str]  = None
        self.instance_id: Optional[int] = None
        self.last_used: float = 0.0
        # Primitivas de concurrencia: evitan lanzar la instancia dos veces
        self._launch_lock = asyncio.Lock()
        self._ready_event = asyncio.Event()


# Singleton compartido por todos los módulos
state = VastaiState()
