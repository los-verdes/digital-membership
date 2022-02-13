#!/usr/bin/env python
import logging
from flask import current_app
from google.cloud.devtools import cloudbuild_v1

from member_card.utils import load_gcp_credentials

logger = logging.getLogger(__name__)


def get_client(credentials=None):
    if credentials is None:
        credentials = load_gcp_credentials()
    return cloudbuild_v1.CloudBuildClient(credentials=credentials)


def generate_upload_statics_build(project_id, repo_name, bucket_id, branch_name="main"):
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
    return build


def create_upload_statics_build(client=None):
    if client is None:
        client = get_client()

    project_id = current_app.config["GCLOUD_PROJECT"]
    repo_name = current_app.config["GCP_REPO_NAME"]
    bucket_id = current_app.config["GCS_BUCKET_ID"]

    upload_statics_build = generate_upload_statics_build(
        project_id=project_id,
        repo_name=repo_name,
        bucket_id=bucket_id,
    )
    return create_build(
        client=client,
        project_id=project_id,
        build=upload_statics_build,
    )


def generate_docker_image_build(project_id, repo_name, image_name, branch_name="main"):
    gcr_name = f"gcr.io/$PROJECT_ID/{image_name}"

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
            "name": "gcr.io/cloud-builders/docker",
            "entrypoint": "bash",
            "args": [
                "-c",
                f"docker pull {gcr_name}:latest || exit 0",
            ],
        },
        {
            "name": "gcr.io/cloud-builders/docker",
            "args": [
                "build",
                "--cache-from",
                f"{gcr_name}:latest",
                "--target",
                image_name,
                "--tag",
                f"{gcr_name}:$SHORT_SHA",
                ".",
            ],
        },
        {
            "name": "gcr.io/cloud-builders/docker",
            "args": [
                "tag",
                f"{gcr_name}:$SHORT_SHA",
                f"{gcr_name}:latest",
            ],
        },
    ]
    build.images = [
        f"{gcr_name}:$SHORT_SHA",
        f"{gcr_name}:latest",
    ]
    return build


def create_docker_image_build(image_name, client=None):
    if client is None:
        client = get_client()

    project_id = current_app.config["GCLOUD_PROJECT"]
    repo_name = current_app.config["GCP_REPO_NAME"]

    docker_image_build = generate_docker_image_build(
        project_id=project_id,
        repo_name=repo_name,
        image_name=image_name,
    )
    return create_build(
        client=client,
        project_id=project_id,
        build=docker_image_build,
    )


def create_build(client, project_id, build):
    operation = client.create_build(
        project_id=project_id,
        build=build,
    )
    logger.debug(f"Cloud build running: {operation.metadata}")
    result = operation.result()
    logger.info(f"Cloud build result: {result.status}")
    return result
