#!/usr/bin/env python
import logging

from google.cloud.devtools import cloudbuild_v1

from member_card.utils import load_gcp_credentials

logger = logging.getLogger(__name__)


def get_client(credentials=None):
    if credentials is None:
        credentials = load_gcp_credentials()
    return cloudbuild_v1.CloudBuildClient(credentials=credentials)


def create_upload_statics_build(
    client, project_id, repo_name, bucket_id, branch_name="main"
):
    build = cloudbuild_v1.Build()
    build.source = {
        "repo_source": {
            "project_id": project_id,
            "repo_name": repo_name,
            "branch_name": branch_name,
        }
    }
    build.steps = [
        {
            "name": "gcr.io/cloud-builders/gsutil",
            "args": [
                "-m",
                "cp",
                "-r",
                "member_card/static/*",
                f"gs://{bucket_id}/static/",
            ],
        },
    ]

    operation = client.create_build(
        project_id=project_id,
        build=build,
    )
    logger.debug(f"Cloud build running: {operation.metadata}")
    result = operation.result()
    logger.info(f"Cloud build result: {result.status}")
    return result
