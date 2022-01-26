import functools
import tempfile
from typing import Callable
from urllib.parse import urlparse
import flask
from logzero import logger

from member_card.db import db, get_or_create
from member_card.models import MembershipCard
from member_card.utils import sign


def with_apple_developer_key() -> Callable:
    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def new_func(*args, **kwargs):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".key") as key_fp:
                logger.info(
                    f"Stashing Apple developer key under a temporary file {key_fp.name=}"
                )
                unformatted_key = flask.current_app.config[
                    "APPLE_DEVELOPER_PRIVATE_KEY"
                ]
                formatted_key = "\n".join(unformatted_key.split("\\n"))
                key_fp.write(formatted_key)
                key_fp.seek(0)
                kwargs["key_filepath"] = key_fp.name
                return method(*args, **kwargs)

        return new_func

    return decorator


def get_or_create_membership_card(user):
    app = flask.current_app
    parsed_base_url = urlparse(flask.request.base_url)
    web_service_url = f"{parsed_base_url.scheme}://{parsed_base_url.netloc}/passkit"
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
        logger.debug("generating QR code for message")
        serial_number = str(membership_card.serial_number)
        qr_code_signature = sign(serial_number)
        qr_code_message = f"Content: {flask.url_for('verify_pass', serial_number=serial_number)}?signature={qr_code_signature}"
        logger.debug(f"{qr_code_message=}")
        setattr(membership_card, 'qr_code_message', qr_code_message)
        db.session.add(membership_card)
        db.session.commit()

    return membership_card


@with_apple_developer_key()
def get_apple_pass_for_user(user, key_filepath=None):

    app = flask.current_app
    apple_pass = get_or_create_membership_card(user=user)
    db.session.add(apple_pass)
    db.session.commit()
    # breakpoint()
    _, pkpass_out_path = tempfile.mkstemp()
    apple_pass.create_pkpass(
        key_filepath=key_filepath,
        key_password=app.config["APPLE_DEVELOPER_PRIVATE_KEY_PASSWORD"],
        pkpass_out_path=pkpass_out_path,
    )
    return pkpass_out_path
