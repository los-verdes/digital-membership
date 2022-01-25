FROM python:3.9

WORKDIR /app

# Various pre-requisites for getting m2crypto install (which in turn is used by passkit)
RUN apt update \
    && apt install -y \
        build-essential \
        python3-dev \
        swig \
    && apt clean

COPY requirements.txt .
RUN pip install \
    --trusted-host pypi.python.org \
    --requirement requirements.txt

COPY ./member_card/ ./member_card
COPY ./*.py ./

ENTRYPOINT ["gunicorn", "-b", "0.0.0.0:8080", "wsgi:create_app()", "--log-file", "-", "--log-level", "info"]
