import logging
from urllib.parse import unquote

import flask_security
from bigcommerce.api import BigcommerceApi
from flask import (
    Blueprint,
    Response,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from member_card.db import db
from member_card.gcp import publish_message
from member_card.models import Store, StoreUser, User
from member_card.models.user import add_role_to_user, ensure_user
from member_card.utils import verify, sign

logger = logging.getLogger(__name__)
bigcommerce_bp = Blueprint("bigcommerce", __name__)


class InvalidBigCommerceWebhookSignature(Exception):
    pass


# @bigcommerce_bp.errorhandler(500)
# def internal_server_error(e):
#     content = "Internal Server Error: " + {e} + "<br>"
#     content += error_info(e)
#     return content, 500


@bigcommerce_bp.errorhandler(400)
def bad_request(e):
    return f"Bad Request: {e} <br>", 400


def client_id():
    return current_app.config["BIGCOMMERCE_CLIENT_ID"]


def client_secret():
    return current_app.config["BIGCOMMERCE_CLIENT_SECRET"]


def jwt_error(e):
    print(f"JWT verification failed: {e}")
    return "Payload verification failed!", 401


@bigcommerce_bp.route("/bigcommerce/order-webhook", methods=["POST"])
def order_webhook():
    webhook_payload = request.get_json()
    if webhook_payload is None:
        # can't very well verify the signature with no signature...
        raise InvalidBigCommerceWebhookSignature(
            "unable to verify notification signature!"
        )
    incoming_signature = (
        request.headers.get("authorization").lower().replace("bearer", "").strip()
    )
    logger.debug(
        f"bigcommerce_order_webhook(): INCOMING WEBHOOK YO {webhook_payload=}",
    )

    data = webhook_payload["data"]
    data_type = webhook_payload["data"]["type"]
    hash = webhook_payload["hash"]
    producer = webhook_payload["producer"]
    scope = webhook_payload["scope"]
    store_id = webhook_payload["store_id"]
    store_hash = producer.split("/", 1)[1]

    log_extra = dict(
        data=data,
        data_type=data_type,
        hash=hash,
        producer=producer,
        scope=scope,
        store_id=store_id,
        store_hash=store_hash,
    )
    logger.debug(
        f"bigcommerce_order_webhook(): {request.data=}",
        extra=log_extra,
    )

    configured_store_hash = current_app.config["BIGCOMMERCE_STORE_HASH"]
    configured_client_id = current_app.config["BIGCOMMERCE_CLIENT_ID"]
    if store_hash != configured_store_hash:
        error_msg = f"Refusing to process webhook payload for {store_hash=} (not in {configured_store_hash=})"
        logger.warning(error_msg, extra=log_extra)
        return error_msg, 403

    logger.debug(
        f"Verifying webhook payload signature ({incoming_signature=})", extra=log_extra
    )

    expected_token_data = f"{configured_store_hash}.{configured_client_id}"
    expected_signature = sign(expected_token_data).lower()
    # is_verified = verify(incoming_signature, expected_token_data)
    # print(f"{is_verified=}")
    # breakpoint()
    if not incoming_signature == expected_signature:
        logger.warning(
            f"Unable to verify {incoming_signature} for {hash=}.",
            extra=log_extra,
        )
        raise InvalidBigCommerceWebhookSignature(
            "unable to verify notification signature!"
        )

    if data_type == "order":
        message_data = dict(
            type="sync_bigcommerce_order",
            data=data,
            data_type=data_type,
            hash=hash,
            producer=producer,
            scope=scope,
            store_id=store_id,
            store_hash=store_hash,
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
        # raise NotImplementedError(f"No handler available for {data_type=}")
        logger.warning(f"No handler available for {data_type=}")
    return "Got it, thanks! :)"


# The Auth Callback URL. See https://developer.bigcommerce.com/api/callback
@bigcommerce_bp.route("/bigcommerce/callback")
def auth_callback():
    redirect_url = url_for(
        "bigcommerce.auth_callback",
        _external=True,
        _scheme="https",
    )
    logger.debug(f"bigc auth_callback(): {redirect_url=}")

    # Put together params for token request
    code = request.args["code"]
    context = request.args["context"]
    scope = request.args["scope"]
    store_hash = context.split("/")[1]

    # Fetch a permanent oauth token. This will throw an exception on error,
    # which will get caught by our error handler above.
    client = BigcommerceApi(client_id=client_id(), store_hash=store_hash)
    token = client.oauth_fetch_token(
        client_secret(), code, context, scope, redirect_url
    )
    bc_user_id = token["user"]["id"]
    bc_username = token["user"]["username"]
    email = token["user"]["email"]
    access_token = token["access_token"]

    # Create or update store
    store = Store.query.filter_by(store_hash=store_hash).first()
    if store is None:
        store = Store(store_hash, access_token, scope)
        db.session.add(store)
        db.session.commit()
    else:
        store.access_token = access_token
        store.scope = scope
        db.session.add(store)
        db.session.commit()
        # If the app was installed before, make sure the old admin user is no longer marked as the admin
        oldadminuser = StoreUser.query.filter_by(store_id=store.id, admin=True).first()
        if oldadminuser:
            oldadminuser.admin = False
            db.session.add(oldadminuser)

    # Create or update global BC user
    user = User.query.filter_by(bigcommerce_id=bc_user_id).first()
    if user is None:
        user = ensure_user(
            email=email,
            username=bc_username,
            bigcommerce_id=bc_user_id,
        )

    add_role_to_user(
        user=user,
        role_name="admin",
    )

    login_result = flask_security.login_user(
        user=user,
        remember=True,
    )
    logger.debug(f"{user=}: ==> {login_result=}")
    logger.debug(f"{user=}: ==> {user.is_authenticated()=}")

    # Create or update store user
    storeuser = StoreUser.query.filter_by(user_id=user.id, store_id=store.id).first()
    if not storeuser:
        storeuser = StoreUser(store, user, admin=True)
    else:
        storeuser.admin = True
    db.session.add(storeuser)
    db.session.commit()

    # Log user in and redirect to app home
    session["storeuserid"] = storeuser.id
    return redirect(
        url_for(
            "admin_dashboard",
            _external=True,
            _scheme="https",
        )
    )


# The Load URL. See https://developer.bigcommerce.com/api/load
@bigcommerce_bp.route("/bigcommerce/load")
def load():
    # Decode and verify payload
    payload = request.args["signed_payload_jwt"]
    try:
        user_data = BigcommerceApi.oauth_verify_payload_jwt(
            payload, client_secret(), client_id()
        )
    except Exception as e:
        return jwt_error(e)

    bc_user_id = user_data["user"]["id"]
    email = user_data["user"]["email"]
    store_hash = user_data["sub"].split("stores/")[1]

    # Lookup store
    store = Store.query.filter_by(store_hash=store_hash).first()
    if store is None:
        return "Store not found!", 401

    # Lookup user and create if doesn't exist (this can happen if you enable multi-user
    # when registering your app)
    user = User.query.filter_by(bigcommerce_id=bc_user_id).first()
    if user is None:
        user = User(bc_user_id, email)
        db.session.add(user)
        db.session.commit()
    storeuser = StoreUser.query.filter_by(user_id=user.id, store_id=store.id).first()
    if storeuser is None:
        storeuser = StoreUser(store, user)
        db.session.add(storeuser)
        db.session.commit()

    # Log user in and redirect to app interface
    session["storeuserid"] = storeuser.id
    return redirect(
        url_for(
            "admin_dashboard",
            _external=True,
            _scheme="https",
        )
    )


# The Uninstall URL. See https://developer.bigcommerce.com/api/load
@bigcommerce_bp.route("/bigcommerce/uninstall")
def uninstall():
    # Decode and verify payload
    payload = request.args["signed_payload_jwt"]
    try:
        user_data = BigcommerceApi.oauth_verify_payload_jwt(
            payload, client_secret(), client_id()
        )
    except Exception as e:
        return jwt_error(e)

    # Lookup store
    store_hash = user_data["sub"].split("stores/")[1]
    store = Store.query.filter_by(store_hash=store_hash).first()
    if store is None:
        return "Store not found!", 401

    # Clean up: delete store associated users. This logic is up to you.
    # You may decide to keep these records around in case the user installs
    # your app again.
    storeusers = StoreUser.query.filter_by(store_id=store.id)
    for storeuser in storeusers:
        db.session.delete(storeuser)
    db.session.delete(store)
    db.session.commit()

    return Response("Deleted", status=204)


# The Remove User Callback URL.
@bigcommerce_bp.route("/bigcommerce/remove-user")
def remove_user():
    payload = request.args["signed_payload_jwt"]
    try:
        user_data = BigcommerceApi.oauth_verify_payload_jwt(
            payload, client_secret(), client_id()
        )
    except Exception as e:
        return jwt_error(e)

    store_hash = user_data["sub"].split("stores/")[1]
    store = Store.query.filter_by(store_hash=store_hash).first()
    if store is None:
        return "Store not found!", 401

    # Lookup user and delete it
    bc_user_id = user_data["user"]["id"]
    user = User.query.filter_by(bigcommerce_id=bc_user_id).first()
    if user is not None:
        storeuser = StoreUser.query.filter_by(
            user_id=user.id, store_id=store.id
        ).first()
        db.session.delete(storeuser)
        db.session.commit()

    return Response("Deleted", status=204)


@bigcommerce_bp.route("/bigcommerce/javascript/<store_hash>.js")
def render_store_script(store_hash):
    return render_template(
        "bigcommerce_membership_card.js.j2",
        store_domain=current_app.config["BIGCOMMERCE_STORE_DOMAIN"],
        member_info_url=unquote(
            url_for(
                "customer_card_html",
                store_hash=current_app.config["BIGCOMMERCE_STORE_HASH"],
                jwt_token=r"${jwt_token}",
                _external=True,
            )
        ),
        app_client_id=current_app.config["BIGCOMMERCE_CLIENT_ID"],
        widget_id=current_app.config["BIGCOMMERCE_WIDGET_ID"],
    )
