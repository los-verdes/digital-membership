import os
import json
from google.cloud.secretmanager import SecretManagerServiceClient

# from logzero import logger
import logging

DEFAULT_SECRET_PLACEHOLDERS = {
    "SLACK_SIGNING_SECRET": os.getenv("SLACK_SIGNING_SECRET"),
    "SECRET_KEY": os.getenv("SECRET_KEY"),
    "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
}


def retrieve_app_secrets(secret_name, defaults=DEFAULT_SECRET_PLACEHOLDERS):
    logging.debug(f"Retrieving app secrets from {secret_name=}")
    if secret_name is None:
        return defaults
    response = SecretManagerServiceClient().access_secret_version(
        request={"name": secret_name}
    )
    payload = response.payload.data.decode("UTF-8")
    app_secrets = json.loads(payload)
    redacted_secrets = {k: v[-4:] for k, v in app_secrets.items()}
    logging.debug(f"secrets received: {redacted_secrets}")
    return app_secrets
