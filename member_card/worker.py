import base64
import json
import logging

from codetiming import Timer
from flask import Blueprint, current_app, request

from member_card.db import db
from member_card.image import generate_and_upload_card_image
from member_card.minibc import Minibc, minibc_orders_etl  # load_single_subscription,
from member_card.models import AnnualMembership, User
from member_card.models.membership_card import get_or_create_membership_card
from member_card.passes import generate_and_upload_apple_pass
from member_card.sendgrid import generate_email_message, send_email_message
from member_card.squarespace import (
    Squarespace,  # squarespace_orders_etl,
    load_single_order,
)

logger = logging.getLogger(__name__)

worker_bp = Blueprint("worker", __name__)


@Timer(name="parse_message")
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
    message = json.loads(
        base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
    )
    logger.debug(f"Parsed message: {message}")
    assert "type" in message, "'type' key required in message pubsub body"
    return message


@Timer(name="process_email_distribution_request")
def process_email_distribution_request(message):
    logger.debug(f"Processing email distribution request message: {message}")
    email_distribution_recipient = message["email_distribution_recipient"]
    log_extra = dict(
        pubsub_message=message,
        email_distribution_recipient=email_distribution_recipient,
    )
    logger.debug("looking up user...", extra=log_extra)
    try:
        # BONUS TODO: make this case-insensitive
        user = User.query.filter_by(email=email_distribution_recipient).one()
        log_extra.update(dict(user=user))
    except Exception as err:
        log_extra.update(dict(user_query_err=err))
        logger.warning(f"unable to look up user!: {err}", extra=log_extra)
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

    membership_card = get_or_create_membership_card(user)

    card_image_url = generate_and_upload_card_image(membership_card)

    apple_pass_url = generate_and_upload_apple_pass(membership_card)

    email_message = generate_email_message(
        membership_card=membership_card,
        card_image_url=card_image_url,
        apple_pass_url=apple_pass_url,
        submitting_ip_address=message.get("remote_addr"),
        submitted_on=message.get("submitted_on"),
    )

    send_email_resp = send_email_message(email_message)
    logger.debug(f"send_email_message() response: {send_email_resp=}")
    return send_email_resp


@Timer(name="sync_subscriptions_etl")
def sync_subscriptions_etl(message, load_all=False):
    log_extra = dict(pubsub_message=message)
    logger.debug(
        f"Processing sync subscriptions ETL message: {message}",
        extra=log_extra,
    )

    total_num_memberships_start = db.session.query(AnnualMembership.id).count()

    # membership_skus = current_app.config["MINIBC_MEMBERSHIP_SUBSCRIPTION_ID"]
    # squarespace = Squarespace(api_key=current_app.config["SQUARESPACE_API_KEY"])
    # memberships = squarespace_orders_etl(
    #     squarespace_client=squarespace,
    #     membership_skus=membership_skus,
    #     load_all=load_all,
    # )

    skus = current_app.config["MINIBC_MEMBERSHIP_SKUS"]
    minibc = Minibc(api_key=current_app.config["MINIBC_API_KEY"])
    # minibc.search_products()
    memberships = minibc_orders_etl(
        minibc_client=minibc,
        skus=skus,
        load_all=load_all,
    )

    total_num_memberships_end = db.session.query(AnnualMembership.id).count()
    log_extra.update(
        dict(
            active_memberships=[m for m in memberships if m.is_active],
            inactive_memberships=[m for m in memberships if not m.is_active],
            total_num_memberships_end=total_num_memberships_end,
            total_num_memberships_added=(
                total_num_memberships_end - total_num_memberships_start
            ),
        )
    )
    logger.info(
        f"Sync subscription aggregate stats: {log_extra['total_num_memberships_added']=}",
        extra=log_extra,
    )
    return {
        "stats": dict(
            num_membership=len(memberships),
            num_active_membership=len(log_extra["active_memberships"]),
            num_inactive_membership=len(log_extra["inactive_memberships"]),
            total_num_memberships_start=total_num_memberships_start,
            total_num_memberships_end=total_num_memberships_end,
            total_num_memberships_added=log_extra["total_num_memberships_added"],
        )
    }


@Timer(name="sync_squarespace_order")
def sync_squarespace_order(message):
    log_extra = dict(pubsub_message=message)
    logger.debug(f"sync_squarespace_order() called with {message=}", extra=log_extra)
    logger.warning("skipping squarespace order syncin...")
    return "nah"
    order_id = message["order_id"]

    membership_skus = current_app.config["SQUARESPACE_MEMBERSHIP_SKUS"]
    squarespace = Squarespace(api_key=current_app.config["SQUARESPACE_API_KEY"])
    memberships = load_single_order(
        squarespace_client=squarespace,
        membership_skus=membership_skus,
        order_id=order_id,
    )
    logger.info(f"Sync for {order_id=} completed!: {memberships=}")
    return memberships


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

    message_type = message["type"]
    if message_type not in MESSAGE_TYPE_HANDLERS:
        return f"Message type {message_type} is unsupported", 400

    MESSAGE_TYPE_HANDLERS[message["type"]](message)
    if Timer.timers:
        for timer_name, timer_duration in Timer.timers.items():
            logger.info(f"- **{timer_name}**: {timer_duration}")
    return ("", 204)
