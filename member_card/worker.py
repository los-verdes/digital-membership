import json
import logging

from flask import Blueprint, request

from member_card.models import User

logger = logging.getLogger(__name__)

worker_bp = Blueprint("worker", __name__)


@worker_bp.route("/pubsub", methods=["POST"])
def pubsub_ingress():
    import base64

    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    pubsub_message = envelope["message"]

    print(f"{isinstance(pubsub_message, dict)=}")
    print(f"{pubsub_message=}")
    message = json.loads(
        base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
    )
    if message.get("type") == "email_distribution_request":

        from member_card.sendgrid import generate_and_send_email

        email_distribution_recipient = message["email_distribution_recipient"]
        log_extra = dict(email_distribution_recipient=email_distribution_recipient)
        logger.debug("looking up user...", extra=log_extra)
        try:
            # BONUS TODO: make this case-insensitive
            user = User.query.filter_by(email=email_distribution_recipient).one()
            log_extra.update(dict(user=user))
        except Exception as err:
            log_extra.update(dict(user_query_err=err))
            logger.warning(
                f"no matching user found for {email_distribution_recipient=}",
                extra=log_extra,
            )
            user = None

        if user and user.has_active_memberships:
            logger.info(
                f"Found {user=} for {email_distribution_recipient=}. Generating and sending email now",
                extra=log_extra,
            )
            generate_and_send_email(
                user=user,
                submitting_ip_address=message.get("remote_addr"),
                submitted_on=message.get("submitted_on"),
            )

    return ("", 204)
