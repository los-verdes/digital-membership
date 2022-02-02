import functools
import logging
import os
import tempfile
from typing import Callable

import flask

from member_card import get_base_url
from member_card.db import db, get_or_create
from member_card.models import MembershipCard
from member_card.utils import sign

DEFAULT_APPLE_KEY_FILEPATH = "/secrets/apple-private.key"


def with_apple_developer_key() -> Callable:
    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def new_func(*args, **kwargs):
            key_filepath = DEFAULT_APPLE_KEY_FILEPATH

            # running_in_cloud_run = os.getenv("K_SERVICE", False)
            running_in_cloud_run = (
                os.getenv("FLASK_ENV", "unknown").lower().strip() == "production"
            )
            if running_in_cloud_run or (
                key_filepath
                and os.path.isfile(key_filepath)
                and os.access(key_filepath, os.R_OK)
            ):
                logging.debug(f"Using {key_filepath=}")
                kwargs["key_filepath"] = key_filepath
                return method(*args, **kwargs)

            if "APPLE_DEVELOPER_PRIVATE_KEY" not in flask.current_app.config:
                error_msg = f"File {key_filepath} doesn't exist or isn't readable _and_ no key found under APPLE_DEVELOPER_PRIVATE_KEY env var!"
                logging.error(error_msg)
                raise Exception(error_msg)

            unformatted_key = flask.current_app.config["APPLE_DEVELOPER_PRIVATE_KEY"]
            logging.warning(
                f"File {key_filepath} doesn't exist or isn't readable, pulling key from environment and stashing in temp file...."
            )
            with tempfile.NamedTemporaryFile(mode="w", suffix=".key") as key_fp:
                logging.info(
                    f"Stashing Apple developer key under a temporary file {key_fp.name=}"
                )
                formatted_key = "\n".join(unformatted_key.split("\\n"))
                key_fp.write(formatted_key)
                key_fp.seek(0)
                kwargs["key_filepath"] = key_fp.name
                return method(*args, **kwargs)

        return new_func

    return decorator


def get_or_create_membership_card(user, base_url=None):
    app = flask.current_app
    if base_url is None:
        base_url = get_base_url()

    web_service_url = f"{base_url}/passkit"
    membership_card = get_or_create(
        session=db.session,
        model=MembershipCard,
        user_id=user.id,
        apple_organization_name=app.config["APPLE_DEVELOPER_TEAM_ID"],
        apple_pass_type_identifier=app.config["APPLE_DEVELOPER_PASS_TYPE_ID"],
        apple_team_identifier=app.config["APPLE_DEVELOPER_TEAM_ID"],
        member_since=user.member_since,
        member_until=user.membership_expiry,
        web_service_url=web_service_url,
    )
    db.session.add(membership_card)
    db.session.commit()

    # TODO: do this more efficient like:
    if not membership_card.qr_code_message:
        logging.debug("generating QR code for message")
        serial_number = str(membership_card.serial_number)
        qr_code_signature = sign(serial_number)
        qr_code_message = f"Content: {base_url}{flask.url_for('verify_pass', serial_number=serial_number)}?signature={qr_code_signature}"
        logging.debug(f"{qr_code_message=}")
        setattr(membership_card, "qr_code_message", qr_code_message)
        db.session.add(membership_card)
        db.session.commit()

    return membership_card


@with_apple_developer_key()
def get_apple_pass_for_user(user, key_filepath=DEFAULT_APPLE_KEY_FILEPATH):
    app = flask.current_app
    apple_pass = get_or_create_membership_card(user=user)
    db.session.add(apple_pass)
    db.session.commit()
    _, pkpass_out_path = tempfile.mkstemp()
    apple_pass.create_pkpass(
        key_filepath=key_filepath,
        key_password=app.config["APPLE_PASS_PRIVATE_KEY_PASSWORD"],
        pkpass_out_path=pkpass_out_path,
    )
    return pkpass_out_path
