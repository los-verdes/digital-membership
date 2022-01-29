#!/usr/bin/env python
try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass

from member_card import create_app

# import logging

# import logzero
# from google_cloud_logger import GoogleCloudFormatter

# Start out with a quiet log level when invoking things this way...
# logzero.loglevel(logging.INFO)
# logzero.formatter(GoogleCloudFormatter)
# logzero.json()

if __name__ == "__main__":
    app = create_app()
    app.run()
