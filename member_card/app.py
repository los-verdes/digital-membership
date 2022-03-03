#!/usr/bin/env python
import binascii
import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_cdn import CDN
from flask_recaptcha import ReCaptcha
from flask_security import Security
from flask_security.core import current_user as current_login_user
from flask_security.decorators import login_required, roles_required
from flask_security.utils import logout_user
from social_flask.template_filters import backends
from social_flask.utils import load_strategy

from member_card import utils
from member_card.db import db
from member_card.models import AnnualMembership
from member_card.models.membership_card import get_or_create_membership_card
from member_card.passes import get_apple_pass_for_user
from member_card.pubsub import publish_message

BASE_DIR = os.path.dirname(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "member_card")
)


app = Flask(__name__)
logger = app.logger
logger.propagate = True

login_manager = utils.MembershipLoginManager()

security = Security()

recaptcha = ReCaptcha()

cdn = CDN()


@app.before_request
def global_user():
    # evaluate proxy value
    g.user = current_login_user._get_current_object()


@app.teardown_appcontext
def commit_on_success(error=None):
    if "sqlalchemy" not in app.extensions:
        # TODO: do this better
        return
    if error is None:
        db.session.commit()
    else:
        db.session.rollback()

    db.session.remove()


@app.context_processor
def inject_user():
    return {
        "user": getattr(g, "user", None),
    }


@app.context_processor
def load_common_context():
    # from member_card.db import get_membership_table_last_sync

    return utils.common_context(
        app.config["SOCIAL_AUTH_AUTHENTICATION_BACKENDS"],
        load_strategy(),
        getattr(g, "user", None),
        app.config.get("SOCIAL_AUTH_GOOGLE_PLUS_KEY"),
        form_error_message=request.args.get("formErrorMessage", ""),
        form_message=request.args.get("formMessage", ""),
        # membership_last_sync=get_membership_table_last_sync(),
    )


app.context_processor(backends)
app.jinja_env.globals["url"] = utils.social_url_for


def active_membership_card_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not g.user.has_active_memberships:
            return redirect(
                url_for("no_active_membership_landing_page", **request.args)
            )

        membership_card = get_or_create_membership_card(g.user)

        return f(*args, membership_card=membership_card, **kwargs)

    return decorated_function


@app.route("/")
@active_membership_card_required
def home(membership_card):
    return render_template(
        "member_card_and_history.html.j2",
        membership_card=membership_card,
        membership_orders=g.user.annual_memberships,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
    )


@app.route("/no-active-membership-found")
@login_required
def no_active_membership_landing_page():
    return render_template(
        "no_membership_landing_page.html.j2",
        user=g.user,
        membership_orders=g.user.annual_memberships,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
    )


@app.route("/edit-user-name", methods=["POST"])
@login_required
def edit_user_name_request():
    log_extra = dict(form=request.form)
    new_first_name = request.form["newFirstName"]
    new_last_name = request.form["newLastName"]
    logger.debug(
        f"edit_user_name_request(): {new_first_name=} {new_last_name=}", extra=log_extra
    )
    form_message = utils.get_message_str("edit_user_name_success")
    setattr(g.user, "fullname", " ".join([new_first_name, new_last_name]))
    setattr(g.user, "first_name", new_first_name)
    setattr(g.user, "last_name", new_last_name)
    db.session.add(g.user)
    db.session.commit()
    logger.debug(f"post-commit: {g.user=}")
    return redirect(f"{url_for('home')}?formMessage={form_message}")


@app.route("/email-distribution-request", methods=["POST"])
def email_distribution_request():
    from email_validator import EmailNotValidError, validate_email

    log_extra = dict(form=request.form)

    # First prerequisite: verified recaptcha stuff:
    if not recaptcha.verify():
        email_form_error_message = utils.get_message_str("captcha_not_verified")
        logger.error(
            "Unable to verify recaptcha, redirecting to login", extra=log_extra
        )
        return redirect(
            f"{url_for('login')}?formErrorMessage={email_form_error_message}"
        )

    email_distribution_recipient = request.form.get("emailDistributionRecipient")
    if email_distribution_recipient is None:
        email_form_error_message = utils.get_message_str(
            "missing_email_distribution_recipient"
        )
        logger.error(
            "Unable to verify recaptcha, redirecting to login", extra=log_extra
        )
        return redirect(
            f"{url_for('login')}?formErrorMessage={email_form_error_message}"
        )

    log_extra.update(dict(email_distribution_recipient=email_distribution_recipient))

    # Second prerequisite: we can actually send to this address
    try:
        # Validate.
        valid = validate_email(email_distribution_recipient)

        # Update with the normalized form.
        email_distribution_recipient = valid.email
        log_extra.update(
            dict(email_distribution_recipient=email_distribution_recipient)
        )
    except EmailNotValidError as err:
        log_extra.update(dict(err=err))
        # email is not valid, exception message is human-readable
        email_form_error_message = str(err)
        logger.error(
            "Unable to validate email, redirecting to login",
            extra=dict(form=request.form),
        )
        return redirect(
            f"{url_for('login')}?formErrorMessage={email_form_error_message}"
        )

    topic_id = app.config["GCLOUD_PUBSUB_TOPIC_ID"]
    logger.info(
        f"publishing email distribution request to pubsub {topic_id=}", extra=log_extra
    )
    publish_message(
        project_id=app.config["GCLOUD_PROJECT"],
        topic_id=topic_id,
        message_data=dict(
            type="email_distribution_request",
            email_distribution_recipient=email_distribution_recipient,
            remote_addr=request.remote_addr,
            submitted_on=datetime.utcnow().isoformat(),
        ),
    )

    return render_template(
        "email_request_landing_page.html.j2",
        submitted_email=email_distribution_recipient,
        submission_response_msg="Request received",
        redirect_home_delay_seconds="45",
    )


@app.route("/passes/google-pay")
@active_membership_card_required
def passes_google_pay(membership_card):
    return redirect(membership_card.google_pass_save_url)


@app.route("/passes/apple-pay")
@active_membership_card_required
def passes_apple_pay(membership_card):
    attachment_filename = f"lv_apple_pass-{g.user.last_name.lower()}.pkpass"
    pkpass_out_path = get_apple_pass_for_user(
        user=g.user,
        membership_card=membership_card,
    )
    return send_file(
        pkpass_out_path,
        attachment_filename=attachment_filename,
        mimetype="application/vnd.apple.pkpass",
        as_attachment=True,
    )


@app.route("/squarespace/oauth/login")
@login_required
@roles_required("admin")
def squarespace_oauth_login():
    import urllib.parse

    url = "https://login.squarespace.com/api/1/login/oauth/provider/authorize"
    state = utils.sign(datetime.utcnow().isoformat())
    session["oauth_state"] = state
    params = {
        "client_id": app.config["SQUARESPACE_CLIENT_ID"],
        "redirect_uri": app.config["SQUARESPACE_OAUTH_REDIRECT_URI"],
        "scope": "website.orders,website.orders.read",
        # "access_type": "offline",
        "state": state,
    }
    url_params = urllib.parse.urlencode(params)
    authorize_url = f"{url}?{url_params}"
    logger.debug(f"{url=} + {url_params=} => {authorize_url}")
    return redirect(authorize_url)


@app.route("/squarespace/oauth/connect")
@roles_required("admin")
def squarespace_oauth_callback():
    from member_card.squarespace import (
        Squarespace,
        ensure_orders_webhook_subscription,
        request_new_oauth_token,
    )

    log_extra = dict(request.args)
    if "code" in log_extra:
        del log_extra["code"]

    if error := request.args.get("error"):
        logger.error(
            f"Squarespace oauth connect error: {error=}",
            extra=log_extra,
        )
        return redirect("/")

    if session.get("oauth_state") != request.args["state"]:
        logger.error(
            f"Squarespace oauth connect error: {session.get('oauth_state')=} does not match {request.args['state']=}",
            extra=log_extra,
        )
        return redirect("/")

    code = request.args["code"]
    logger.debug(
        f"squarespace_oauth_callback: {list(request.args)=}",
        extra=log_extra,
    )
    logger.debug(
        f"squarespace_oauth_callback: {list(request.headers)=}",
        extra=log_extra,
    )

    token_resp = request_new_oauth_token(
        client_id=app.config["SQUARESPACE_CLIENT_ID"],
        client_secret=app.config["SQUARESPACE_CLIENT_SECRET"],
        code=code,
        redirect_uri=app.config["SQUARESPACE_OAUTH_REDIRECT_URI"],
    )
    log_extra.update({k: v for k, v in token_resp.items() if not k.endswith("_token")})
    token_account_id = token_resp["account_id"]
    logger.debug(f"squarespace_oauth_callback(): {token_account_id=}", extra=log_extra)

    squarespace = Squarespace(api_key=token_resp["access_token"])
    webhook_subscriptions = ensure_orders_webhook_subscription(
        squarespace=squarespace,
        account_id=token_account_id,
        endpoint_url=app.config["SQUARESPACE_ORDER_WEBHOOK_ENDPOINT"],
    )
    log_extra.update(
        dict(
            webhook_subscriptions=webhook_subscriptions,
        )
    )
    logger.debug(
        f"Webhook listing (after ensuring webhooks): {webhook_subscriptions=}",
        extra=log_extra,
    )

    logger.debug(
        "Sending test notifications for all configured webhooks now...",
        extra=log_extra,
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
            extra=log_extra,
        )
    return redirect(url_for("squarespace_extension_details"))


@app.route("/squarespace/extension-details")
@roles_required("admin")
def squarespace_extension_details():
    from member_card.models import SquarespaceWebhook

    webhooks = SquarespaceWebhook.query.order_by(
        SquarespaceWebhook.created_on.desc()
    ).all()
    logger.debug(f"Webhook entries in the database: {webhooks=}")
    return render_template(
        "squarespace_extension_details.html.j2",
        webhooks=webhooks,
    )


@app.route("/squarespace/order-webhook", methods=["POST"])
def squarespace_order_webhook():
    from member_card.models import SquarespaceWebhook

    webhook_payload = request.get_json()

    incoming_signature = request.headers.get("Squarespace-Signature")
    webhook_id = webhook_payload["subscriptionId"]
    website_id = webhook_payload["websiteId"]
    allowed_website_ids = app.config["SQUARESPACE_ALLOWED_WEBSITE_IDS"]

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
        f"Query database for extant webhook matching {webhook_id=} ({website_id=})",
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
        return "unable to verify notification signature!", 401

    webhook_topic = webhook_payload["topic"]

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

        topic_id = app.config["GCLOUD_PUBSUB_TOPIC_ID"]
        log_extra.update(
            dict(
                message_data=message_data,
                topic_id=topic_id,
            )
        )
        logger.info(
            f"publishing sync_order message to pubsub {topic_id=} with data: {message_data=}",
            extra=log_extra,
        )
        publish_message(
            project_id=app.config["GCLOUD_PROJECT"],
            topic_id=topic_id,
            message_data=message_data,
        )
    else:
        raise NotImplementedError(f"No handler available for {webhook_topic=}")
    return "thanks buds!", 200


@app.route("/verify-pass/<serial_number>")
@login_required
# Note: get_or_create_membership_card() has this route hard-coded in it
# TODO: ^ make that not the case
def verify_pass(serial_number):
    from member_card.models import AnnualMembership, MembershipCard

    signature = request.args.get("signature")
    if not signature:
        return "Unable to verify signature!", 401

    signature_verified = utils.verify(signature=signature, data=serial_number)
    if not signature_verified:
        return "Unable to verify signature!", 401

    verified_card = (
        db.session.query(MembershipCard).filter_by(serial_number=serial_number).one()
    )
    logger.debug(f"{verified_card=}")

    return render_template(
        "apple_pass_validation.html.j2",
        validating_user=g.user,
        verified_card=verified_card,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
    )


@app.route("/login")
def login():
    """Logout view"""
    return render_template(
        "login.html.j2",
        recaptcha_site_key=app.config["RECAPTCHA_SITE_KEY"],
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route("/privacy-policy")
def privacy_policy():
    return render_template(
        "privacy_policy.html.j2",
    )


@app.route("/about")
def about():
    return render_template(
        "about.html.j2",
    )
