"""Logging setup for the music agent. Writes a rotating file under logs/ (git-ignored)."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "agent.log"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(path: Optional[Path] = None, console: bool = False) -> Path:
    """
    Attach a file handler (and optionally a console handler) to the 'musicagent' logger.
    Safe to call more than once. If the log file cannot be created, logging degrades to
    the console instead of crashing the program.
    """
    logger = logging.getLogger("musicagent")
    logger.setLevel(logging.INFO)
    log_path = Path(path or LOG_PATH)

    if not any(getattr(h, "_musicagent", False) for h in logger.handlers):
        handler: logging.Handler
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(log_path, maxBytes=500_000, backupCount=2, encoding="utf-8")
        except OSError:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(FORMAT))
        handler._musicagent = True  # marker so repeat calls do not stack handlers
        logger.addHandler(handler)

    if console and not any(getattr(h, "_console", False) for h in logger.handlers):
        stream = logging.StreamHandler()
        stream.setLevel(logging.WARNING)
        stream.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        stream._console = True
        logger.addHandler(stream)
    return log_path
