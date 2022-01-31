#!/bin/bash

set -eou pipefail

gunicorn \
  --bind=0.0.0.0:8080 \
  --log-file=- \
  --log-level=info \
  --log-config=config/gunicron_logging.ini \
  'wsgi:create_app()'
