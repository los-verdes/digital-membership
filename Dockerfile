FROM python:3.9

WORKDIR /app

# Various pre-requisites for getting m2crypto install (which in turn is used by passkit)
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential=12.9 \
        python3-dev=3.9.2-3 \
        swig=4.0.2-1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

COPY requirements.in .
RUN pip install \
        --no-cache-dir \
        --trusted-host pypi.python.org \
        --requirement requirements.txt \
        google-python-cloud-debugger==2.18

COPY ./config/ ./config
COPY ./member_card/ ./member_card
COPY ./*.py ./
COPY ./scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
