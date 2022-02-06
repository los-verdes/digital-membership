import logging
import tempfile

import flask

from member_card.apple_wallet import with_apple_developer_key
from member_card.db import db
from member_card.models.membership_card import get_or_create_membership_card
from member_card.storage import upload_file_to_gcs

logger = logging.getLogger(__name__)


class MemberCardPass(object):
    pass


@with_apple_developer_key()
def get_apple_pass_for_user(user, apple_pass=None, key_filepath=None):
    app = flask.current_app
    if apple_pass is None:
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


def generate_and_upload_apple_pass(user, membership_card, bucket):
    local_apple_pass_path = get_apple_pass_for_user(
        user=user, apple_pass=membership_card
    )
    remote_apple_pass_path = f"membership-cards/apple-passes/{membership_card.apple_pass_serial_number}.pkpass"
    apple_pass_url = f"{bucket.id}/{remote_apple_pass_path}"
    blob = upload_file_to_gcs(
        bucket=bucket,
        local_file=local_apple_pass_path,
        remote_path=remote_apple_pass_path,
        content_type="application/vnd.apple.pkpass",
    )
    logger.info(
        f"{local_apple_pass_path=} uploaded for {user=}: {apple_pass_url=} ({blob=})"
    )
    return apple_pass_url
