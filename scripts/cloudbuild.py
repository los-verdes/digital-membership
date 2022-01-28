#!/usr/bin/env python
from google.cloud.devtools import cloudbuild_v1
from logzero import logger

from google_apis import load_credentials


def get_client(credentials=None):
    if credentials is None:
        credentials = load_credentials()
    # return cloudbuild_v1.CloudBuildClient(credentials=credentials)
    return cloudbuild_v1.CloudBuildClient()


def trigger_build(client, project_id, repo_name):
    build = cloudbuild_v1.Build()
    # repo_source = cloudbuild_v1.RepoSource()
    # repo_source.project_id =
    build.source = {
        "repo_source": {
            "project_id": project_id,
            "repo_name": repo_name,
            "dir_": "events_page",
            "branch_name": "main",
        }
    }
    build.steps = [
        {
            "name": "python:3.9",
            "entrypoint": "pip",
            "args": ["install", "-r", "requirements.txt", "--user"],
        },
        {
            "name": "python:3.9",
            "entrypoint": "python",
            "args": ["build_static_site.py"],
        },
    ]
    # Reference: https://stackoverflow.com/a/53074972
    # build.artifacts = {
    #     "objects": {
    #         "location": f"gs://{static_site_bucket}",
    #         "paths": [
    #             "events_page/build/*",
    #             "events_page/build/static/*",
    #         ],
    #     }
    # }
    operation = client.create_build(
        project_id=project_id,
        build=build,
    )
    logger.debug(f"Cloud build running: {operation.metadata}")
    result = operation.result()
    logger.info(f"Cloud build result: {result.status}")
    return result
