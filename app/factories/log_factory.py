import logging
import os
from logging.handlers import RotatingFileHandler

def get_logger(name, log_file=None, level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        if log_file is None:
            log_file = f"{name}.log"

        os.makedirs("logs", exist_ok=True)
        file_path = os.path.join("logs", log_file)

        handler = RotatingFileHandler(file_path, maxBytes=10**6, backupCount=5)
        formatter = logging.Formatter(
            "[%(asctime)s] {%(name)s}: %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
