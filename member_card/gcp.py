"""Publishes multiple messages to a Pub/Sub topic with an error handler."""
import json
import logging
import os
from concurrent import futures

from flask import current_app
from google.cloud.secretmanager import SecretManagerServiceClient
from google.cloud import pubsub_v1, storage

logger = logging.getLogger(__name__)


DEFAULT_GCP_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
]

DEFAULT_SECRET_PLACEHOLDERS = {
    "SLACK_SIGNING_SECRET": os.getenv("SLACK_SIGNING_SECRET"),
    "SECRET_KEY": os.getenv("SECRET_KEY"),
    "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
}


# from base64 import b64decode as b64d
# import google.auth
# from google.auth import impersonated_credentials
# from google.oauth2 import service_account
# def load_gcp_credentials(scopes=DEFAULT_GCP_SCOPES):
#     credentials, _ = google.auth.default(scopes=scopes)
#     if service_account_info := current_app.config["SERVICE_ACCOUNT_KEY"]:
#         credentials = service_account.Credentials.from_service_account_info(
#             json.loads(b64d(service_account_info).decode()), scopes=scopes
#         )
#     if sa_email := os.getenv("DIGITAL_MEMBERSHIP_SA_EMAIL"):
#         logging.info(f"Impersonating service account: {sa_email}")
#         source_credentials = credentials
#         target_principal = sa_email
#         credentials = impersonated_credentials.Credentials(
#             source_credentials=source_credentials,
#             target_principal=target_principal,
#             target_scopes=scopes,
#             lifetime=500,
#         )
#     return credentials


def publish_message(project_id, topic_id, message_data):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    data = json.dumps(message_data).encode("utf-8")
    publish_future = publisher.publish(topic_path, data)

    # Wait for all the publish futures to resolve before exiting.
    futures.wait([publish_future], return_when=futures.ALL_COMPLETED)

    logger.info(f"Published messages with error handler to {topic_path}.")


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


def get_gcs_client(credentials=None):
    # if credentials is None:
    #     credentials = load_gcp_credentials()
    return storage.Client(credentials=credentials)


def get_bucket(client=None):
    if client is None:
        client = get_gcs_client()
    return client.get_bucket(current_app.config["GCS_BUCKET_ID"])


def upload_file_to_gcs(local_file, remote_path, content_type=None):
    blob = get_bucket().blob(remote_path)
    if content_type is not None:
        blob.content_type = content_type
    blob.cache_control = "no-cache"

    logger.debug(f"Uploading {local_file=}) to {remote_path=}")

    blob.upload_from_filename(local_file)

    return blob


# from datetime import timedelta
# def get_presigned_url(blob, expiration: "timedelta"):
#     url = blob.generate_signed_url(
#         version="v4",
#         # This URL is valid for 15 minutes
#         expiration=expiration,
#         # Allow GET requests using this URL.
#         method="GET",
#         credentials=load_gcp_credentials(),
#     )
#     logger.info(f"GCS signed URL for {blob=}: {url=}")
#     return url
