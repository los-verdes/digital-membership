#!/usr/bin/env python
try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass

import logging

import logzero

from member_card import create_app

# Start out with a quiet log level when invoking things this way...
logzero.loglevel(logging.INFO)

if __name__ == "__main__":
    app = create_app()
    app.run()
