FROM --platform=linux/amd64 python:3.9 AS worker

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED True

WORKDIR /app

# Various pre-requisites for getting m2crypto install (which in turn is used by passkit)
RUN mkdir --parents /etc/apt/keyrings/ \
  && chmod 0755 /etc/apt/keyrings/ \
  && bash -c 'set -o pipefail && wget -O- https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor > /etc/apt/keyrings/google-chrome.gpg \
    && chmod 644 /etc/apt/keyrings/google-chrome.gpg' \
    && sh -c 'echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        google-chrome-stable \
        build-essential=12.9 \
        libpython3-dev \
        fonts-liberation=1:1.07.4-11 \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install \
        --no-cache-dir \
        --trusted-host pypi.python.org \
        --requirement requirements.txt \
        swig \
        google-python-cloud-debugger==2.18

COPY ./config/ ./config
COPY ./member_card/ ./member_card
COPY ./*.py ./

CMD ["gunicorn", "--bind=:8080", "--workers=1", "--threads=8", "--timeout=0", "--log-config=config/gunicron_logging.ini", "--log-file=-", "wsgi:create_worker_app()"]

FROM --platform=linux/amd64 python:3.9 AS website

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED True

WORKDIR /app

COPY --from=worker /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
COPY ./config/ ./config
COPY ./member_card/ ./member_card
COPY ./*.py ./

CMD ["gunicorn", "--bind=:8080", "--workers=1", "--threads=8", "--timeout=0", "--log-config=config/gunicron_logging.ini", "--log-file=-", "wsgi:create_app()"]
