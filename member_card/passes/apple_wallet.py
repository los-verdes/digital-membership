import functools
import flask
import logging
import os
import tempfile
from typing import Callable

DEFAULT_APPLE_KEY_FILEPATH = "/apple-secrets/private.key"

logger = logging.getLogger(__name__)


def with_apple_developer_key() -> Callable:
    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def new_func(*args, **kwargs):
            key_filepath = flask.current_app.config["APPLE_KEY_FILEPATH"]

            # running_in_cloud_run = os.getenv("K_SERVICE", False)
            running_in_cloud_run = (
                os.getenv("FLASK_ENV", "unknown").lower().strip() == "production"
            )
            if running_in_cloud_run or (
                key_filepath
                and os.path.isfile(key_filepath)
                and os.access(key_filepath, os.R_OK)
            ):
                logger.debug(f"Using {key_filepath=}")
                kwargs["key_filepath"] = key_filepath
                return method(*args, **kwargs)

            if "APPLE_DEVELOPER_PRIVATE_KEY" not in flask.current_app.config:
                error_msg = f"File {key_filepath} doesn't exist or isn't readable _and_ no key found under APPLE_DEVELOPER_PRIVATE_KEY env var!"
                logger.error(error_msg)
                raise Exception(error_msg)

            unformatted_key = flask.current_app.config["APPLE_DEVELOPER_PRIVATE_KEY"]
            logger.warning(
                f"File {key_filepath} doesn't exist or isn't readable, pulling key from environment and stashing in temp file...."
            )
            with tempfile.NamedTemporaryFile(mode="w", suffix=".key") as key_fp:
                logger.info(
                    f"Stashing Apple developer key under a temporary file {key_fp.name=}"
                )
                formatted_key = "\n".join(unformatted_key.split("\\n"))
                key_fp.write(formatted_key)
                key_fp.seek(0)
                kwargs["key_filepath"] = key_fp.name
                return method(*args, **kwargs)

        return new_func

    return decorator
