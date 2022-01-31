#!/usr/bin/env python
import logging
import os

import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler, setup_logging

from member_card import create_app

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass


log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str)

excluded_loggers = (
    "google.cloud",
    "google.auth",
    "google_auth_httplib2",
    "google.api_core.bidi",
    "urllib3",
    "werkzeug",
)
if running_on_cloud_run := "K_SERVICE" in os.environ:
    setup_logging(
        handler=CloudLoggingHandler(google.cloud.logging.Client()),
        log_level=log_level,
        excluded_loggers=excluded_loggers,
    )
else:
    logging.basicConfig(level=log_level)
    for logger_name in excluded_loggers:
        # prevent excluded loggers from propagating logs to handler
        logger = logging.getLogger(logger_name)
        logger.propagate = False

if __name__ == "__main__":
    app = create_app()
    app.run()
