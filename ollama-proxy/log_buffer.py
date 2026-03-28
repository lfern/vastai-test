"""Buffer de logs en memoria para exponerlos via /admin/logs y la UI web."""
import logging
from collections import deque
from datetime import datetime

_MAX_LINES = 500

_buffer: deque[dict] = deque(maxlen=_MAX_LINES)


class _BufferHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord):
        _buffer.append({
            "time":  datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
            "level": record.levelname,
            "msg":   record.getMessage(),
            "line":  self.format(record),
        })


def setup():
    """Añade el handler de buffer al logger raíz. Llamar una sola vez al arrancar."""
    root = logging.getLogger()
    root.addHandler(_BufferHandler())


def get_recent(n: int = 150) -> list[dict]:
    return list(_buffer)[-n:]
