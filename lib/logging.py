"""Zentrales Logging-Setup für das wai-Backend.

Genutzt von gateway, agents/* und mcp_servers/*. Initialisiert einen
Root-Logger 'wai' mit stdout + File-Handler (Pfad via env LOG_FILE,
Default 'logs/app.log').

Nutzung:
    from lib.logging import setup_logging, get_logger
    setup_logging()
    log = get_logger(__name__)
    log.info("nachricht user=%r", user)
"""
import logging
import os
import sys
from pathlib import Path


_FORMAT = "[%(asctime)s] %(levelname)-7s %(name)s — %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"
_configured = False


def setup_logging(level: str | None = None, log_file: str | None = None) -> None:
    """Konfiguriert den 'wai'-Logger. Idempotent — mehrfacher Aufruf no-op."""
    global _configured
    if _configured:
        return

    lvl = level or os.environ.get("LOG_LEVEL", "INFO")
    file_path = log_file or os.environ.get("LOG_FILE", "logs/app.log")
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)
    root = logging.getLogger("wai")
    root.setLevel(lvl)
    root.handlers.clear()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    file_handler = logging.FileHandler(file_path)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Holt einen Child-Logger unter dem 'wai'-Namespace."""
    if not name.startswith("wai"):
        name = f"wai.{name}"
    return logging.getLogger(name)
