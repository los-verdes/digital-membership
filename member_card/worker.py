import base64
import json
import logging

from flask import Blueprint, current_app, request

from member_card.db import db, squarespace_orders_etl
from member_card.models import User
from member_card.sendgrid import generate_and_send_email
from member_card.squarespace import Squarespace

logger = logging.getLogger(__name__)

worker_bp = Blueprint("worker", __name__)


def parse_message():
    envelope = request.get_json()
    logger.debug(f"parsing message within {envelope=}")
    if not envelope:
        msg = "no Pub/Sub message received"
        print(f"error: {msg}")
        raise Exception(f"Bad Request: {msg}")

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        raise Exception(f"Bad Request: {msg}")

    pubsub_message = envelope["message"]
    logger.debug(f"pubsub message from within envelope: {pubsub_message=}")
    print(pubsub_message["data"])
    message = json.loads(
        base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
    )
    assert "type" in message, "'type' key required in message pubsub body"
    return message


def process_email_distribution_request(message):
    logger.debug(f"Processing email distribution request message: {message}")
    email_distribution_recipient = message["email_distribution_recipient"]
    log_extra = dict(
        message=message,
        email_distribution_recipient=email_distribution_recipient,
    )
    logger.debug("looking up user...", extra=log_extra)
    try:
        # BONUS TODO: make this case-insensitive
        user = User.query.filter_by(email=email_distribution_recipient).one()
        log_extra.update(dict(user=user))
    except Exception as err:
        log_extra.update(dict(user_query_err=err))
        user = None

    if user is None:
        logger.warning(
            f"no matching user found for {email_distribution_recipient=}. Exiting early...",
            extra=log_extra,
        )
        return

    if not user.has_active_memberships:
        logger.warning(
            f"{user=} has not active memberships! Exiting early...",
            extra=log_extra,
        )
        return

    logger.info(
        f"Found {user=} for {email_distribution_recipient=}. Generating and sending email now",
        extra=log_extra,
    )
    generate_and_send_email(
        user=user,
        submitting_ip_address=message.get("remote_addr"),
        submitted_on=message.get("submitted_on"),
    )


def sync_subscriptions_etl(message):
    log_extra = dict(message=message)
    logger.debug(
        f"Processing sync subscriptions ETL message: {message}", extra=log_extra,
    )
    membership_skus = current_app.config["SQUARESPACE_MEMBERSHIP_SKUS"]
    squarespace = Squarespace(api_key=current_app.config["SQUARESPACE_API_KEY"])
    etl_results = squarespace_orders_etl(
        squarespace_client=squarespace,
        db_session=db.session,
        membership_skus=membership_skus,
        load_all=False,
    )
    log_extra["etl_results"] = etl_results
    logger.info(f"sync_subscriptions() => {etl_results=}", extra=log_extra)


def sync_squarespace_order(message):
    log_extra = dict(message=message)
    logger.debug(f"sync_squarespace_order() called with {message=}", extra=log_extra)
    # TODO: implement this :D


@worker_bp.route("/pubsub", methods=["POST"])
def pubsub_ingress():
    try:
        message = parse_message()
    except Exception as err:
        return str(err), 400

    MESSAGE_TYPE_HANDLERS = {
        "email_distribution_request": process_email_distribution_request,
        "sync_subscriptions_etl": sync_subscriptions_etl,
        "sync_squarespace_order": sync_squarespace_order,
    }
    MESSAGE_TYPE_HANDLERS[message["type"]](message)

    return ("", 204)
