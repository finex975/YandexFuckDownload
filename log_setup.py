"""Настройка логирования в файл с ротацией."""
import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logger(app_dir: str) -> logging.Logger:
    log_dir = os.path.join(app_dir, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        # Если не можем создать папку — пишем в никуда
        logger = logging.getLogger("ymd")
        logger.addHandler(logging.NullHandler())
        return logger

    log_path = os.path.join(log_dir, "app.log")

    logger = logging.getLogger("ymd")
    logger.setLevel(logging.INFO)

    # Не дублируем хэндлеры при повторных вызовах
    if logger.handlers:
        return logger

    try:
        handler = RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except Exception:
        logger.addHandler(logging.NullHandler())

    return logger