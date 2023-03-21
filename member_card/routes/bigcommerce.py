import logging

import flask_security
from bigcommerce.api import BigcommerceApi
from flask import Blueprint, Response, current_app, redirect, request, session, url_for

from member_card.db import db
from member_card.models import Store, StoreUser, User
from member_card.models.user import add_role_to_user, ensure_user

logger = logging.getLogger(__name__)
bigcommerce_bp = Blueprint("bigcommerce", __name__)


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


# The Auth Callback URL. See https://developer.bigcommerce.com/api/callback
@bigcommerce_bp.route("/bigcommerce/callback")
def auth_callback():
    # Put together params for token request
    code = request.args["code"]
    context = request.args["context"]
    scope = request.args["scope"]
    store_hash = context.split("/")[1]
    redirect_url = current_app.config["BASE_URL"] + url_for("bigcommerce.auth_callback")
    logger.debug(f"bigc auth_callback(): {redirect_url=}")
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
    return redirect(url_for("admin_dashboard"))


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
    return redirect(url_for("admin_dashboard"))


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
