#!/usr/bin/env python
import logging
import os

import google.cloud.logging  # Don't conflict with standard logging
from google.cloud.logging.handlers import CloudLoggingHandler, setup_logging

from member_card import create_app

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass


log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.getLogger().setLevel(getattr(logging, log_level))
setup_logging(CloudLoggingHandler(google.cloud.logging.Client()))

if __name__ == "__main__":
    app = create_app()
    app.run()
