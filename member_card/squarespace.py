import binascii
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import requests
from dateutil.parser import parse
from flask import current_app, request, session
from requests.auth import HTTPBasicAuth

from member_card import utils
from member_card.db import db, get_or_create, get_or_update
from member_card.models import SquarespaceWebhook, table_metadata
from member_card.models.user import ensure_user
from member_card.gcp import publish_message

if TYPE_CHECKING:
    from collections.abc import Iterable

__VERSION__ = "0.0.4"
api_baseurl = "https://api.squarespace.com"
api_version = "1.0"

logger = logging.getLogger(__name__)


class InvalidSquarespaceWebhookSignature(Exception):
    pass


def process_order_webhook_payload():
    webhook_payload = request.get_json()
    if webhook_payload is None:
        # can't very well verify the signature with no signature...
        raise InvalidSquarespaceWebhookSignature(
            "unable to verify notification signature!"
        )
    incoming_signature = request.headers.get("Squarespace-Signature")
    webhook_id = webhook_payload["subscriptionId"]
    website_id = webhook_payload["websiteId"]
    allowed_website_ids = current_app.config["SQUARESPACE_ALLOWED_WEBSITE_IDS"]

    log_extra = dict(
        incoming_signature=incoming_signature,
        webhook_payload=webhook_payload,
        allowed_website_ids=allowed_website_ids,
        website_id=website_id,
        request_data=request.data,
    )
    logger.debug(
        f"squarespace_order_webhook(): INCOMING WEBHOOK YO {webhook_payload=}",
        extra=log_extra,
    )
    logger.debug(
        f"squarespace_order_webhook(): {request.data=}",
        extra=log_extra,
    )

    if website_id not in allowed_website_ids:
        error_msg = f"Refusing to process webhook payload for {website_id=} (not in {allowed_website_ids=})"
        logger.warning(error_msg, extra=log_extra)
        return error_msg, 403

    logger.debug(
        f"Querying database for extant webhook matching {webhook_id=} ({website_id=})",
        extra=log_extra,
    )
    webhook = SquarespaceWebhook.query.filter_by(
        webhook_id=webhook_id, website_id=website_id
    ).one()
    log_extra["webhook"] = webhook
    logger.debug(f"{webhook_id}: {webhook=}", extra=log_extra)
    logger.debug(
        f"Verifying webhook payload signature ({incoming_signature=})", extra=log_extra
    )
    signature_key = binascii.unhexlify(webhook.secret.encode("utf-8"))
    payload_verified = utils.verify_hex_digest(
        signature=incoming_signature,
        data=request.data,
        key=signature_key,
    )
    log_extra["payload_verified"] = payload_verified
    if not payload_verified:
        expected_signature = utils.sign(
            data=request.data,
            key=signature_key,
            use_hex_digest=True,
        )
        log_extra["expected_signature"] = expected_signature
        logger.warning(
            f"Unable to verify {incoming_signature} for {webhook_id} ({expected_signature=}).",
            extra=log_extra,
        )
        raise InvalidSquarespaceWebhookSignature(
            "unable to verify notification signature!"
        )

    webhook_topic = webhook_payload["topic"]
    website_id = webhook_payload["websiteId"]

    if webhook_topic == "extension.uninstall":
        logger.debug(f"{webhook_topic=} => deleting {webhook=} from database...")
        db.session.delete(webhook)
        db.session.commit()
    elif webhook_topic.startswith("order."):
        message_data = dict(
            type="sync_squarespace_order",
            notification_id=webhook_payload["id"],
            order_id=webhook_payload["data"]["orderId"],
            website_id=website_id,
            created_on=webhook_payload["createdOn"],
        )

        topic_id = current_app.config["GCLOUD_PUBSUB_TOPIC_ID"]
        log_extra = dict(
            message_data=message_data,
            topic_id=topic_id,
        )

        logger.info(
            f"publishing sync_order message to pubsub {topic_id=} with data: {message_data=}",
            extra=log_extra,
        )
        publish_message(
            project_id=current_app.config["GCLOUD_PROJECT"],
            topic_id=topic_id,
            message_data=message_data,
        )
    else:
        raise NotImplementedError(f"No handler available for {webhook_topic=}")
    return webhook


def generate_oauth_authorize_url():
    base_url = "https://login.squarespace.com/api/1/login/oauth/provider/authorize"

    state = utils.sign(datetime.utcnow().isoformat())
    session["oauth_state"] = state

    params = {
        "client_id": current_app.config["SQUARESPACE_CLIENT_ID"],
        "redirect_uri": current_app.config["SQUARESPACE_OAUTH_REDIRECT_URI"],
        "scope": "website.orders,website.orders.read",
        "state": state,
    }
    url_params = urllib.parse.urlencode(params)

    authorize_url = f"{base_url}?{url_params}"

    logger.debug(f"{base_url=} + {url_params=} => {authorize_url}")

    return authorize_url


def insert_order_as_membership(order, membership_skus):
    from member_card.models import AnnualMembership

    membership_orders = []
    line_items = order.get("lineItems", [])
    subscription_line_items = [i for i in line_items if i["sku"] in membership_skus]
    ignored_line_items = [i for i in line_items if i["sku"] not in membership_skus]
    logger.debug(f"{ignored_line_items=}")
    for subscription_line_item in subscription_line_items:
        fulfilled_on = None
        if fulfilled_on := order.get("fulfilledOn"):
            fulfilled_on = parse(fulfilled_on).replace(tzinfo=timezone.utc)

        customer_email = order["customerEmail"]

        membership_kwargs = dict(
            order_id=order["id"],
            order_number=order["orderNumber"],
            channel=order["channel"],
            channel_name=order["channelName"],
            billing_address_first_name=order["billingAddress"]["firstName"],
            billing_address_last_name=order["billingAddress"]["lastName"],
            external_order_reference=order["externalOrderReference"],
            created_on=parse(order["createdOn"]).replace(tzinfo=timezone.utc),
            modified_on=parse(order["modifiedOn"]).replace(tzinfo=timezone.utc),
            fulfilled_on=fulfilled_on,
            customer_email=customer_email,
            fulfillment_status=order["fulfillmentStatus"],
            test_mode=order["testmode"],
            line_item_id=subscription_line_item["id"],
            sku=subscription_line_item["sku"],
            variant_id=subscription_line_item["variantId"],
            product_id=subscription_line_item["productId"],
            product_name=subscription_line_item["productName"],
        )
        membership = get_or_update(
            session=db.session,
            model=AnnualMembership,
            filters=["order_id", "order_number"],
            kwargs=membership_kwargs,
        )
        membership_orders.append(membership)

        membership_user = ensure_user(
            email=membership.customer_email,
            first_name=membership.billing_address_first_name,
            last_name=membership.billing_address_last_name,
        )
        membership_user_id = membership_user.id
        if not membership.user_id:
            logger.debug(
                f"No user_id set for {membership=}! Setting to: {membership_user_id=}"
            )
            setattr(membership, "user_id", membership_user_id)
    return membership_orders


def parse_subscription_orders(membership_skus, subscription_orders):
    logger.info(f"{len(subscription_orders)=} retrieved from Squarespace...")

    # Insert oldest orders first (so our internal membership ID generally aligns with order IDs...)
    subscription_orders.reverse()

    # Loop over all the raw order data and do the ETL bits
    memberships = []
    for subscription_order in subscription_orders:
        membership_orders = insert_order_as_membership(
            order=subscription_order,
            membership_skus=membership_skus,
        )
        for membership_order in membership_orders:
            db.session.add(membership_order)
        db.session.commit()
        memberships += membership_orders
    return memberships


def squarespace_orders_etl(squarespace_client, membership_skus, load_all):
    from member_card import models

    etl_start_time = datetime.now(tz=ZoneInfo("UTC"))

    membership_table_name = models.AnnualMembership.__tablename__

    if not load_all:
        last_run_start_time = table_metadata.get_last_run_start_time(
            membership_table_name
        )
        logger.info(f"Starting sync from {last_run_start_time=}")
        subscription_orders = squarespace_client.load_membership_orders_datetime_window(
            membership_skus=membership_skus,
            modified_before=last_run_start_time,
            modified_after=last_run_start_time - timedelta(days=1),
        )

    else:
        logger.info("Loading ALL orders now...")
        subscription_orders = squarespace_client.load_all_membership_orders(
            membership_skus=membership_skus,
        )

    memberships = parse_subscription_orders(membership_skus, subscription_orders)

    table_metadata.set_last_run_start_time(membership_table_name, etl_start_time)

    return memberships


def load_single_order(squarespace_client, membership_skus, order_id):
    subscription_order = squarespace_client.order(order_id)
    logger.debug(f"API response for {order_id=}: {subscription_order=}")
    memberships = parse_subscription_orders(
        membership_skus=membership_skus,
        subscription_orders=[subscription_order],
    )
    logger.debug(f"After parsing subscription orders: {memberships=}")
    return memberships


def validate_oauth_connect_request():
    invariants = [
        (
            request.args.get("error", None) is not None,
            utils.get_message_str("squarespace_oauth_connect_error"),
        ),
        (
            "state" not in request.args,
            utils.get_message_str("squarespace_oauth_connect_missing_state"),
        ),
        (
            session.get("oauth_state") != request.args.get("state"),
            utils.get_message_str("squarespace_oauth_state_mismatch"),
        ),
        (
            "code" not in request.args,
            utils.get_message_str("squarespace_oauth_connect_missing_code"),
        ),
    ]

    for invariant in invariants:
        condition, error_message = invariant
        if condition:
            logger.error(error_message)
            raise Exception(error_message)


def get_client_from_oauth_code(code):
    validate_oauth_connect_request()
    token_resp = request_new_oauth_token(
        client_id=current_app.config["SQUARESPACE_CLIENT_ID"],
        client_secret=current_app.config["SQUARESPACE_CLIENT_SECRET"],
        code=code,
        redirect_uri=current_app.config["SQUARESPACE_OAUTH_REDIRECT_URI"],
    )
    log_extra = {k: v for k, v in token_resp.items() if not k.endswith("_token")}
    token_account_id = token_resp["account_id"]
    logger.debug(f"squarespace_oauth_callback(): {token_account_id=}", extra=log_extra)
    squarespace = Squarespace(
        api_key=token_resp["access_token"], account_id=token_account_id
    )
    return squarespace


def ensure_orders_webhook_subscription(code, endpoint_url, delete_extant_first=False):
    squarespace = get_client_from_oauth_code(code)
    if delete_extant_first:
        list_webhooks_resp = squarespace.list_webhook_subscriptions()
        webhook_subscriptions = list_webhooks_resp["webhookSubscriptions"]
        logger.debug(f"ensure_orders_webhook_subscription(): {webhook_subscriptions=}")

        for webhook_subscription in webhook_subscriptions:
            tmp_delete_resp = squarespace.delete_webhook(
                webhook_id=webhook_subscription["id"]
            )
            logger.debug(f"{tmp_delete_resp=}")

    list_webhooks_resp = squarespace.list_webhook_subscriptions()
    webhook_subscriptions = list_webhooks_resp["webhookSubscriptions"]
    logger.debug(f"ensure_orders_webhook_subscription(): {webhook_subscriptions=}")

    if webhook_subscriptions:
        for webhook_subscription in webhook_subscriptions:
            rotate_secret_for_webhook(
                squarespace=squarespace,
                webhook_subscription=webhook_subscription,
                account_id=squarespace.account_id,
            )
    else:
        order_webhook = create_orders_webhook(
            squarespace=squarespace,
            account_id=squarespace.account_id,
            endpoint_url=endpoint_url,
        )

        logger.debug("Refreshing webhooks list post-webhook-creation...")
        list_webhooks_resp = squarespace.list_webhook_subscriptions()
        webhook_subscriptions = list_webhooks_resp["webhookSubscriptions"]
        webhook_subscriptions_by_id = {w["id"]: w for w in webhook_subscriptions}
        logger.debug(f"after creating webhook: {webhook_subscriptions_by_id=}")
        website_id = webhook_subscriptions_by_id[order_webhook.webhook_id]["websiteId"]
        logger.debug(f"Setting website_id for {order_webhook} to: {website_id=}")
        setattr(order_webhook, "website_id", website_id)
        db.session.add(order_webhook)
        db.session.commit()
        logger.debug(f"order webhook committed!: {order_webhook=}")

    send_test_notifications_for_webhooks(squarespace, webhook_subscriptions)

    return webhook_subscriptions


def rotate_secret_for_webhook(squarespace, webhook_subscription, account_id):
    webhook_id = webhook_subscription["id"]
    logger.debug(
        f"Querying database for extant webhook ID (or creating a new entry): {webhook_id}..."
    )
    order_webhook = get_or_create(
        session=db.session,
        model=SquarespaceWebhook,
        webhook_id=webhook_id,
        account_id=account_id,
        endpoint_url=webhook_subscription["endpointUrl"],
        # topics=orders_webhook_resp["topics"],
        # created_on=webhook_subscription["createdOn"],
        # updated_on=webhook_subscription["updatedOn"],
    )

    setattr(order_webhook, "topics", webhook_subscription["topics"])
    setattr(order_webhook, "created_on", webhook_subscription["createdOn"])
    setattr(order_webhook, "updated_on", webhook_subscription["updatedOn"])
    website_id = webhook_subscription["websiteId"]
    logger.debug(f"Setting website_id for {order_webhook} to: {website_id=}")
    setattr(order_webhook, "website_id", website_id)
    # order_webhook = SquarespaceWebhook.query.filter_by(
    #     webhook_id=webhook_id, account_id=account_id
    # ).one()

    logger.debug(f"Rotating webhook subscription secret for {order_webhook=}...")
    rotate_secret_resp = squarespace.rotate_webhook_subscription_secret(
        webhook_id=order_webhook.webhook_id
    )

    logger.debug(f"Updating secret attribute for webhook {webhook_id}...")
    setattr(order_webhook, "secret", rotate_secret_resp["secret"])
    db.session.add(order_webhook)
    db.session.commit()
    logger.debug(f"Secret attribute update for webhook {webhook_id} committed!")


def create_orders_webhook(squarespace, account_id, endpoint_url):
    # I.e., if we have no extant webhook subscriptions for the targeted site / account ID...
    logger.debug(f"Creating webhook for {account_id} now...")
    orders_webhook_resp = squarespace.create_webhook(
        endpoint_url=endpoint_url,
        topics=[
            "order.create",
            "order.update",
            "extension.uninstall",
        ],
    )
    logger.debug(f"create_orders_webhook(): {orders_webhook_resp=}")

    order_webhook = get_or_create(
        session=db.session,
        model=SquarespaceWebhook,
        webhook_id=orders_webhook_resp["id"],
        account_id=account_id,
        endpoint_url=orders_webhook_resp["endpointUrl"],
        # topics=orders_webhook_resp["topics"],
        secret=orders_webhook_resp["secret"],
        # created_on=orders_webhook_resp["createdOn"],
        # updated_on=orders_webhook_resp["updatedOn"],
    )
    logger.debug(f"order webhook created!: {order_webhook=}")
    setattr(order_webhook, "topics", orders_webhook_resp["topics"])
    setattr(order_webhook, "created_on", orders_webhook_resp["createdOn"])
    setattr(order_webhook, "updated_on", orders_webhook_resp["updatedOn"])
    return order_webhook


def send_test_notifications_for_webhooks(squarespace, webhook_subscriptions):
    logger.debug(
        "Sending test notifications for all configured webhooks now...",
    )
    for webhook_subscription in webhook_subscriptions:
        webhook_id = webhook_subscription["id"]
        logger.debug(f"Sending test notifications for webhook {webhook_id}...")
        test_notification_resp = squarespace.send_test_webhook_notification(
            webhook_id=webhook_id,
            topic="order.create",
        )
        logger.debug(
            f"Test notifications for webhook {webhook_id}: {test_notification_resp=}",
        )


def perform_oauth_token_request(client_id, client_secret, token_request_body):
    access_token_url = "https://login.squarespace.com/api/1/login/oauth/provider/tokens"

    token_request_auth = HTTPBasicAuth(
        username=client_id,
        password=client_secret,
    )

    token_resp = requests.post(
        url=access_token_url,
        json=token_request_body,
        auth=token_request_auth,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "lv-digital-membership",
        },
    )
    logger.debug(f"perform_oauth_token_request(): {list(token_resp.headers)=}")
    token_resp.raise_for_status()
    resp_data = token_resp.json()
    # {
    #     "access_token": "<ACCESS-TOKEN>",
    #     "access_token_expires_at": 1645033666.058,
    #     "account_id": "61d0825ac2dd1a52b2e29b66",
    #     "expires_in": 1799,
    #     "refresh_token": "<REFRESH-TOKEN>",
    #     "refresh_token_expires_at": 1645636666.053,
    #     "session_expires_at": 1647555455.432,
    #     "session_id": "620c267f1c5a7f6358b71e88",
    #     "token": "<ACCESS-TOKEN>",
    #     "token_type": "bearer",
    # }
    for k, v in resp_data.items():
        if k.endswith("expires_at"):
            expires_at_dt = datetime.fromtimestamp(v).strftime("%c")
            logger.debug(f"perform_oauth_token_request(): {k} => {expires_at_dt}")
            resp_data[k] = expires_at_dt
    return resp_data


def request_new_oauth_token(client_id, client_secret, code, redirect_uri):
    token_request_body = dict(
        grant_type="authorization_code",
        redirect_uri=redirect_uri,
        code=code,
    )
    return perform_oauth_token_request(
        client_id=client_id,
        client_secret=client_secret,
        token_request_body=token_request_body,
    )


def refresh_oauth_token(client_id, client_secret, refresh_token):
    token_request_body = dict(
        grant_type="refresh_token",
        refresh_token=refresh_token,
    )
    return perform_oauth_token_request(
        client_id=client_id,
        client_secret=client_secret,
        token_request_body=token_request_body,
    )


class SquarespaceError(Exception):
    pass


class Squarespace(object):
    """Represents orders from a particular squarespace store.

    :api_key:
        Your Squarespace API key. Required.

    :api_baseurl:
        The baseuri for the Squarespace API. You shouldn't need to change
        this.

    :api_version:
        The version of the Squarespace API to target. If you change this
        without making any code changes you may break this library.
    """

    def __init__(
        self,
        api_key,
        api_baseurl=api_baseurl,
        api_version=api_version,
        account_id=None,
    ):
        self.api_key = api_key
        self.api_baseurl = api_baseurl
        self.api_version = api_version
        self.account_id = account_id

        # Setup our HTTP session
        self.http = requests.Session()
        self.http.headers.update({"Authorization": "Bearer " + self.api_key})
        self.useragent = "Squarespace python API v%s by Zach White." % __VERSION__
        self._next_page = None

    @property
    def useragent(self):
        """Get the current useragent."""
        return self._useragent

    @useragent.setter
    def useragent(self, agent_string):
        """Set the User-Agent that will be used."""
        self._useragent = agent_string
        self.http.headers.update({"User-Agent": self._useragent})

    def post(self, path, object):
        """Post an `object` to the Squarespace API.

        :object:
            A dictionary containing JSON compatible key/value combinations.
        """
        url = "%s/%s/%s" % (self.api_baseurl, self.api_version, path)
        # logger.debug("url:%s object:%s", url, object)
        return self.process_request(self.http.post(url, json=object))

    def get(self, path, args=None) -> dict:
        """Retrieve an endpoint from the Squarespace API."""
        if not args:
            args = {}

        url = "%s/%s/%s" % (self.api_baseurl, self.api_version, path)
        # logger.debug("url:%s args:%s", url, args)
        return self.process_request(self.http.get(url, params=args))

    def delete(self, path):
        url = "%s/%s/%s" % (self.api_baseurl, self.api_version, path)
        # logger.debug("url:%s object:%s", url, object)
        return self.process_request(self.http.delete(url))

    def process_request(self, request) -> dict:
        """Process a request and return the data."""
        if request.status_code in [200, 201]:
            return request.json()
        elif request.status_code == 204:
            return dict()
        elif request.status_code == 401:
            raise ValueError("The API key %s is not valid.", self.api_key)
        elif 200 < request.status_code < 299:
            logger.warning("Squarespace success response %s:", request.status_code)
            logger.warning(request.text)
            raise NotImplementedError(
                "Squarespace sent us a success response we're not prepared for!"
            )

        logger.error("Squarespace error response %s:", request.status_code)
        logger.error("URL: %s", request.url)
        logger.error(request.text)

        if 400 <= request.status_code < 499:
            raise RuntimeError("Squarespace thinks this request is bogus")
        if 500 <= request.status_code < 599:
            raise RuntimeError("Squarespace is having problems, try later.")

        raise RuntimeError("An unknown error occurred fetching your request.")

    def get_profile_by_email(self, email):
        return self.get(path="profiles/", args=dict(filter=f"email,{email}"))

    def order(self, order_id=None, order_number=None):
        """Retrieve a single order."""
        if order_id:
            return self.get("commerce/orders/" + order_id)
        elif order_number:
            for order in self.all_orders():
                if order["orderNumber"] == order_number:
                    return order
        else:
            raise SquarespaceError(
                "You must specify one of `order_id` or `order_number`"
            )

    def orders(self, **args):
        """Retrieve the 20 latest orders, by modification date."""
        uri = "commerce/orders"

        result = self.get(uri, args)
        self._next_page = (
            result["pagination"]["nextPageCursor"]
            if "nextPageCursor" in result["pagination"]
            else None
        )
        # breakpoint()
        return result["result"]

    def next_page(self) -> "Iterable":
        """Retrieve the next 20 orders, or None if there are no more orders."""
        return self.orders(cursor=self._next_page) if self._next_page else iter([])

    def all_orders(self, **args):
        orders = self.orders(**args)
        for order in orders:
            yield order

        count = 0
        while self._next_page:
            count += 1
            for order in self.next_page():
                yield order

    def load_membership_orders_datetime_window(
        self,
        membership_skus,
        modified_before=None,
        modified_after=None,
    ):
        order_params = dict()
        if modified_after is not None:
            order_params = dict(
                modifiedAfter=modified_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                modifiedBefore=modified_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

        return self.load_all_membership_orders(
            membership_skus, order_params=order_params
        )

    def load_all_membership_orders(self, membership_skus, order_params=None):
        # ) -> List[AnnualMembership]:
        # remove "None"s
        if order_params is None:
            order_params = {}
        order_params = {k: v for k, v in order_params.items() if v is not None}

        all_orders = []
        membership_orders = []

        logger.debug(f"Grabbing all orders with {order_params=}")

        for order in self.all_orders(**order_params):
            all_orders.append(order)

            order_product_names = [i["productName"] for i in order["lineItems"]]
            if any(i["sku"] in membership_skus for i in order["lineItems"]):
                logger.debug(
                    f"{order['id']=} (#{order['orderNumber']}) includes {membership_skus=} in {order_product_names=}"
                )
                membership_orders.append(order)
                continue
            # logger.debug(
            #     f"#{order['orderNumber']} has no {membership_sku=} in {order_product_names=}"
            # )

        logger.debug(
            f"{len(all_orders)=} loaded with {len(membership_orders)=} and whatnot"
        )
        return membership_orders

    def list_webhook_subscriptions(
        self,
    ):
        logger.debug("Sending 'Retrieve all webhook subscriptions' request...")
        return self.get(
            path="webhook_subscriptions",
        )

    def delete_webhook(
        self,
        webhook_id,
    ):
        webhook_path = f"webhook_subscriptions/{webhook_id}"

        logger.debug(
            f"Sending 'Delete a webhook subscription' request for {webhook_id=}..."
        )
        return self.delete(
            path=webhook_path,
        )

    def create_webhook(
        self,
        endpoint_url,
        topics,
    ):
        request_body = dict(
            endpointUrl=endpoint_url,
            topics=topics,
        )

        logger.debug(
            f"Sending 'Create a webhook subscription' request with {request_body=}..."
        )
        return self.post(
            path="webhook_subscriptions",
            object=request_body,
        )

    def rotate_webhook_subscription_secret(
        self,
        webhook_id,
    ):
        rotate_secret_path = f"webhook_subscriptions/{webhook_id}/actions/rotateSecret"

        logger.debug(
            f"Sending 'Rotate a subscription secret' request for {webhook_id=}..."
        )
        return self.post(path=rotate_secret_path, object=dict())

    def send_test_webhook_notification(
        self,
        webhook_id,
        topic,
    ):
        test_notification_path = (
            f"webhook_subscriptions/{webhook_id}/actions/sendTestNotification"
        )

        logger.debug(
            f"Sending 'Rotate a subscription secret' request for {webhook_id=}..."
        )
        return self.post(path=test_notification_path, object=dict(topic=topic))
