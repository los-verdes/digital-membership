#!/usr/bin/env python
import os

import google.auth
from google.auth import impersonated_credentials
from google.cloud import firestore
from logzero import logger

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform	",
]


def load_credentials(scopes=DEFAULT_SCOPES):
    credentials, _ = google.auth.default(scopes=scopes)
    if sa_email := os.getenv("DIGITAL_MEMBERSHIP_SA_EMAIL"):
        logger.debug(f"Using credentials from impersonated service account: {sa_email}")
        source_credentials = credentials
        target_principal = sa_email
        credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=target_principal,
            target_scopes=scopes,
            lifetime=500,
        )
    return credentials


def get_firestore_client(credentials=None):
    if credentials is None:
        credentials = load_credentials()
    return firestore.Client(credentials=credentials)
