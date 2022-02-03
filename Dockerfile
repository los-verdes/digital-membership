FROM python:3.9 AS base

WORKDIR /app

# Various pre-requisites for getting m2crypto install (which in turn is used by passkit)
RUN sh -c 'set -o pipefail && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -' \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential=12.9 \
        python3-dev=3.9.2-3 \
        swig=4.0.2-1 \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install \
        --no-cache-dir \
        --trusted-host pypi.python.org \
        --requirement requirements.txt \
        google-python-cloud-debugger==2.18

FROM python:3.9-slim AS website

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED True

WORKDIR /app

COPY --from=base /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
COPY ./config/ ./config
COPY ./member_card/ ./member_card
COPY ./*.py ./

CMD ["exec", "gunicorn", "--bind=:$PORT", "--workers=1", "--threads=8", "--timeout=0", "--log-config=config/gunicron_logging.ini", "wsgi:create_app()"]

FROM base AS worker

ENV PYTHONUNBUFFERED True

WORKDIR /app

RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        fonts-liberation=1:1.07.4-11 \
        google-chrome-stable=98.0.4758.80-1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=base /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
COPY ./config/ ./config
COPY ./member_card/ ./member_card
COPY ./*.py ./

CMD ["exec", "gunicorn", "--bind=:$PORT", "--workers=1", "--threads=8", "--timeout=0", "--log-config=config/gunicron_logging.ini", "wsgi:create_app()"]
