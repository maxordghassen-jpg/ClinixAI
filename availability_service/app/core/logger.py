"""
Logging utility
"""

import logging
import os

from app.core.config import settings


def get_logger(name: str) -> logging.Logger:
    """
    Create and configure logger
    """

    # Create logs directory
    os.makedirs(
        settings.LOG_DIR,
        exist_ok=True
    )

    # Create logger
    logger = logging.getLogger(name)

    logger.setLevel(
        getattr(logging, settings.LOG_LEVEL)
    )

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # File handler
    log_path = os.path.join(
        settings.LOG_DIR,
        settings.LOG_FILE
    )

    file_handler = logging.FileHandler(
        log_path,
        encoding="utf-8"
    )

    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()

    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger