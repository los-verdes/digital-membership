#!/bin/bash

set -eou pipefail

gunicorn \
  --bind=0.0.0.0:8080 \
  --log-file=- \
  --log-level=info \
  --timeout=0 \
  --preload \
  --log-config=config/gunicron_logging.ini \
  'wsgi:create_app()'
