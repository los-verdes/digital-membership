import logging
import os
import tempfile
from contextlib import contextmanager

from flask import current_app

logger = logging.getLogger(__name__)


@contextmanager
def tmp_apple_developer_key():
    key_filepath = current_app.config["APPLE_KEY_FILEPATH"]
    if os.path.exists(key_filepath):
        yield key_filepath
        return

    unformatted_key = current_app.config.get("APPLE_DEVELOPER_PRIVATE_KEY")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".key") as key_fp:
        logger.info(
            f"Stashing Apple developer key under a temporary file {key_fp.name=}"
        )
        formatted_key = "\n".join(unformatted_key.split("\\n"))
        key_fp.write(formatted_key)
        key_fp.seek(0)
        yield key_fp.name
        return
