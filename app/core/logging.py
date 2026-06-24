"""Configuracion de logging homogenea."""
from __future__ import annotations

import logging
from logging.config import dictConfig


def configure_logging(log_level: str = "INFO") -> None:
    log_level = log_level.upper()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(levelname)s | %(asctime)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "loggers": {
                "app": {"handlers": ["console"], "level": log_level, "propagate": False},
            },
            "root": {"handlers": ["console"], "level": "WARNING"},
        }
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
