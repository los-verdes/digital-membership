import base64
import json
import logging

from flask import Blueprint, current_app, request

from member_card import slack
from member_card.bigcommerce import (
    bigcommerce_orders_etl,
    get_app_client_for_store,
    load_all_bigcommerce_orders,
)
from member_card.db import db
from member_card.image import ensure_uploaded_card_image
from member_card.models import AnnualMembership
from member_card.models.user import get_user_or_none
from member_card.models.membership_card import get_or_create_membership_card
from member_card.passes import generate_and_upload_apple_pass
from member_card.sendgrid import generate_email_message, send_email_message

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
    message = json.loads(
        base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
    )
    logger.debug(f"Parsed message: {message}")
    assert "type" in message, "'type' key required in message pubsub body"
    return message


def process_email_distribution_request(message):
    logger.debug(f"Processing email distribution request message: {message}")
    email_distribution_recipient = message["email_distribution_recipient"]
    log_extra = dict(
        pubsub_message=message,
        email_distribution_recipient=email_distribution_recipient,
    )
    user = get_user_or_none(
        email_address=email_distribution_recipient,
        log_extra=log_extra,
    )
    if user is None:
        logger.warning(
            "process_email_distribution_request() :: no user found, returning early..."
        )
        return

    logger.info(
        f"Found {user=} for {email_distribution_recipient=}. Generating and sending email now",
        extra=log_extra,
    )

    membership_card = get_or_create_membership_card(user)

    card_image_url = ensure_uploaded_card_image(membership_card)

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


def process_ensure_uploaded_card_image_request(message):
    logger.debug(f"Processing ensure_uploaded_card_image message: {message}")
    member_email_address = message["member_email_address"]
    log_extra = dict(
        pubsub_message=message,
        member_email_address=member_email_address,
    )
    user = get_user_or_none(
        email_address=member_email_address,
        log_extra=log_extra,
    )
    if user is None:
        logger.warning(
            "ensure_uploaded_card_image_worker() :: no user found, returning early..."
        )
        return

    logger.info(
        f"Found {user=} for {member_email_address=}. Ensuring generated card image has been uploaded now...",
        extra=log_extra,
    )

    membership_card = get_or_create_membership_card(user)

    card_image_url = ensure_uploaded_card_image(membership_card)

    logger.debug(f"ensure_uploaded_card_image(): {card_image_url=}")
    return card_image_url


def sync_subscriptions_etl(message, load_all=False):
    log_extra = dict(pubsub_message=message)
    logger.debug(
        f"Processing sync subscriptions ETL message: {message}",
        extra=log_extra,
    )

    total_num_memberships_start = db.session.query(AnnualMembership.id).count()

    membership_skus = current_app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"]
    store_hash = current_app.config["BIGCOMMERCE_STORE_HASH"]
    bigcommerce_client = get_app_client_for_store(store_hash=store_hash)

    if load_all:
        memberships = load_all_bigcommerce_orders(
            bigcommerce_client=bigcommerce_client,
            membership_skus=membership_skus,
        )

    else:
        memberships = bigcommerce_orders_etl(
            bigcommerce_client=bigcommerce_client,
            membership_skus=membership_skus,
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


def sync_squarespace_order(message):
    log_extra = dict(pubsub_message=message)
    logger.debug(f"sync_squarespace_order() called with {message=}", extra=log_extra)
    logger.warning("skipping squarespace order syncin...")
    return "nah"


def run_slack_members_etl(message):
    log_extra = dict(pubsub_message=message)
    logger.debug(f"run_slack_members_etl() called with {message=}", extra=log_extra)
    slack_client = slack.get_web_client()
    slack_users = slack.slack_members_etl(
        client=slack_client,
    )
    return slack_users


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
        "run_slack_members_etl": run_slack_members_etl,
        "ensure_uploaded_card_image_request": process_ensure_uploaded_card_image_request,
    }

    message_type = message["type"]
    if message_type not in MESSAGE_TYPE_HANDLERS:
        return f"Message type {message_type} is unsupported", 400

    MESSAGE_TYPE_HANDLERS[message["type"]](message)
    return ("", 204)
