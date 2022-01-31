#!/usr/bin/env python
import logging
import os

import google.cloud.logging
from google.cloud.logging.handlers import (
    CloudLoggingHandler,
    setup_logging,
    EXCLUDED_LOGGER_DEFAULTS,
)

from member_card import create_app

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass


log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str)

excluded_loggers = EXCLUDED_LOGGER_DEFAULTS[:]
excluded_loggers += [
    "urllib3",
]
setup_logging(
    handler=CloudLoggingHandler(google.cloud.logging.Client()),
    log_level=log_level,
    excluded_loggers=excluded_loggers,
)

if __name__ == "__main__":
    app = create_app()
    app.run()
