FROM python:3.9 AS base

WORKDIR /app

# Various pre-requisites for getting m2crypto install (which in turn is used by passkit)
RUN apt-get update \
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

COPY --from=base /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./config/ ./config
COPY ./member_card/ ./member_card
COPY ./*.py ./
COPY ./scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh
ENTRYPOINT ["./scripts/docker-entrypoint.sh"]

# FROM website AS worker
