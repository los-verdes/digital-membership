#!/usr/bin/env python
import glob
import json
import logging
import os
from base64 import b64decode as b64d
from datetime import timedelta

import flask
import google.auth
from google.auth import impersonated_credentials
from google.cloud import storage
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
]


def load_credentials(scopes=DEFAULT_SCOPES):
    credentials, _ = google.auth.default(scopes=scopes)
    if service_account_info := flask.current_app.config["SERVICE_ACCOUNT_KEY"]:
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(b64d(service_account_info).decode()), scopes=scopes
        )
    if sa_email := os.getenv("DIGITAL_MEMBERSHIP_SA_EMAIL"):
        logger.info(f"Impersonating service account: {sa_email}")
        source_credentials = credentials
        target_principal = sa_email
        credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=target_principal,
            target_scopes=scopes,
            lifetime=500,
        )
    return credentials


def get_client(credentials=None):
    if credentials is None:
        credentials = load_credentials()
    return storage.Client()


def upload_build_to_gcs(client, bucket_id, prefix):
    if prefix is None:
        prefix = ""
    bucket = client.get_bucket(bucket_id)
    build_dir_path = os.path.abspath(os.path.join(BASE_DIR, "..", "build/"))
    logger.info(f"Uploading {build_dir_path=} to {bucket=} ({prefix=})")
    upload_local_directory_to_gcs(client, build_dir_path, bucket, prefix)
    logger.info(f"{build_dir_path=} upload to {bucket=} ({prefix=}) completed!")


def remove_subpath_from_gcs(client, bucket_id, prefix):
    bucket = client.get_bucket(bucket_id)
    blobs_to_delete = bucket.list_blobs(prefix=prefix)
    for blob in blobs_to_delete:
        blob.delete()
    # bucket.delete_blobs(blobs_to_delete)
    # logger.info(f"{len(list(blobs_to_delete))=} deleted from gs://{bucket_id}/{prefix}")
    logger.info(f"All blobs deleted from gs://{bucket_id}/{prefix}")


def upload_local_directory_to_gcs(client, local_path, bucket, gcs_path):
    assert os.path.isdir(local_path)
    for local_file in glob.glob(local_path + "/**"):
        if not os.path.isfile(local_file):
            upload_local_directory_to_gcs(
                client,
                local_file,
                bucket,
                os.path.join(gcs_path, os.path.basename(local_file)),
            )
        else:
            upload_file_to_gcs(
                bucket=bucket,
                local_file=local_file,
                remote_path=os.path.join(gcs_path, os.path.basename(local_file)),
            )


def upload_file_to_gcs(bucket, local_file, remote_path, content_type=None):
    blob = bucket.blob(remote_path)
    if content_type is not None:
        blob.content_type = content_type
    blob.cache_control = "no-cache"
    logger.debug(f"Uploading {local_file=}) to {remote_path=}")
    # logger.debug(f"Uploading {blob=} ({local_file=}) to: {bucket=}")
    blob.upload_from_filename(local_file)
    return blob


def get_presigned_url(blob, expiration: "timedelta"):
    url = blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=expiration,
        # Allow GET requests using this URL.
        method="GET",
        credentials=load_credentials(),
    )
    logger.info(f"GCS signed URL for {blob=}: {url=}")
    return url
