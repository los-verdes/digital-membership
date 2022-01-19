FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install \
    --trusted-host pypi.python.org \
    --requirement requirements.txt

COPY ./member_card/ ./member_card

ENTRYPOINT ["gunicorn", "-b", "0.0.0.0:8080", "member_card.app:create_app()", "--log-file", "-"]
