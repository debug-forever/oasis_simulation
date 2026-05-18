import logging
from pathlib import Path


DEBUG_LOG_PATH = Path(__file__).resolve().parents[1] / "debug_startup.log"


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def append_debug(prefix: str, message: str) -> None:
    try:
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(f"[{prefix}] {message}\n")
    except OSError:
        pass
