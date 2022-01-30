#!/usr/bin/env python
import os
import logging

import click

from member_card import create_app

from logging.config import dictConfig


try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass


class RemoveColorFilter(logging.Filter):
    def filter(self, record):
        if record and record.msg and isinstance(record.msg, str):
            record.msg = click.unstyle(record.msg)
        return True


running_on_cloud_run = "K_SERVICE" in os.environ
dictConfig(
    {
        "version": 1,
        "filters": {
            "no_color": {
                "()": RemoveColorFilter,
            }
        },
        "formatters": {
            "json": {
                "()": "google_cloud_logger.GoogleCloudFormatter",
                "application_info": {
                    "type": "python-application",
                    "name": "digital-membership",
                },
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            },
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "default": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "json": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["no_color"],
            },
        },
        "loggers": {
            "": {
                "level": os.getenv("LOG_LEVEL", "INFO").upper(),
                "handlers": ["json"] if running_on_cloud_run else ["default"],
                "propagate": False,
            },
            "member_card": {
                "level": os.getenv("LOG_LEVEL", "INFO").upper(),
                "handlers": ["json"] if running_on_cloud_run else ["default"],
            },
        },
    }
)

if __name__ == "__main__":
    app = create_app()
    app.run()
