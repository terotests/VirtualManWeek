import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from ..config import appdata_root

LOG_FILENAME = "action.log"


def get_logger() -> logging.Logger:
    logger = logging.getLogger("virtualmanweek")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    log_dir = appdata_root()
    path = log_dir / LOG_FILENAME

    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    return logger
