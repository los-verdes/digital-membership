#!/usr/bin/env python

from member_card import create_app

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass

if __name__ == "__main__":
    app = create_app()
    app.run()
