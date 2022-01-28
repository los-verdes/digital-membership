#!/usr/bin/env python

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass

from member_card import create_app

if __name__ == "__main__":
    app = create_app()
    app.run()
