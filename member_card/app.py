#!/usr/bin/env python
import os
from datetime import datetime
import binascii
import click
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
from sqlalchemy.sql import func

from member_card import utils
from member_card.models import User

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


# @login_manager.user_loader
# def load_user(userid):
#     try:
#         return User.query.get(int(userid))
#     except (TypeError, ValueError):
#         pass


@app.before_request
def global_user():
    # evaluate proxy value
    g.user = current_login_user._get_current_object()


@app.teardown_appcontext
def commit_on_success(error=None):
    if "sqlalchemy" not in app.extensions:
        # TODO: do this better
        return
    from member_card.db import db

    if error is None:
        db.session.commit()
    else:
        db.session.rollback()

    db.session.remove()


@app.context_processor
def inject_user():
    try:
        return {"user": g.user}
    except AttributeError:
        return {"user": None}


@app.context_processor
def load_common_context():
    # from member_card.db import get_membership_table_last_sync

    return utils.common_context(
        app.config["SOCIAL_AUTH_AUTHENTICATION_BACKENDS"],
        load_strategy(),
        getattr(g, "user", None),
        app.config.get("SOCIAL_AUTH_GOOGLE_PLUS_KEY"),
        # membership_last_sync=get_membership_table_last_sync(),
    )


app.context_processor(backends)
app.jinja_env.globals["url"] = utils.social_url_for


@app.route("/")
@login_required
def home():
    from member_card.models import AnnualMembership

    current_user = g.user
    if not current_user.is_authenticated:
        return redirect("/login")

    if current_user.has_active_memberships:
        from member_card.models.membership_card import get_or_create_membership_card

        membership_card = get_or_create_membership_card(current_user)
        # response_body = render_template(
        # TODO: update this deal to only generate gpay pass JWTs upon demand instead of every request
        return render_template(
            "member_card_and_history.html.j2",
            membership_card=membership_card,
            membership_orders=g.user.annual_memberships,
            membership_table_keys=list(AnnualMembership().to_dict().keys()),
        )
    else:
        return render_template(
            "no_membership_landing_page.html.j2",
            user=current_user,
            membership_orders=g.user.annual_memberships,
            membership_table_keys=list(AnnualMembership().to_dict().keys()),
        )


@app.route("/edit-user-name", methods=["POST"])
def edit_user_name_request():

    log_extra = dict(form=request.form)
    new_first_name = request.form["newFirstName"]
    new_last_name = request.form["newLastName"]
    logger.debug(
        f"edit_user_name_request(): {new_first_name=} {new_last_name=}", extra=log_extra
    )
    return redirect("/")


@app.route("/email-distribution-request", methods=["POST"])
def email_distribution_request():
    from email_validator import EmailNotValidError, validate_email

    from member_card.pubsub import publish_message

    log_extra = dict(form=request.form)

    # First prerequisite: verified recaptcha stuff:
    if not recaptcha.verify():
        email_form_error_message = "Request not verified via ReCaptcha! Please try again or contact support@losverd.es for assistance."
        logger.error(
            "Unable to verify recaptcha, redirecting to login", extra=log_extra
        )
        return redirect(
            f"{url_for('login')}?emailFormErrorMessage={email_form_error_message}"
        )

    email_distribution_recipient = request.form["emailDistributionRecipient"]
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
            f"{url_for('login')}?emailFormErrorMessage={email_form_error_message}"
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


@login_required
@app.route("/passes/google-pay")
def passes_google_pay():

    current_user = g.user
    if current_user.is_authenticated:
        from member_card.models.membership_card import get_or_create_membership_card

        membership_card = get_or_create_membership_card(current_user)
        return redirect(membership_card.google_pass_save_url)

    return redirect("/")


@login_required
@app.route("/passes/apple-pay")
def passes_apple_pay():

    current_user = g.user
    if current_user.is_authenticated:
        from member_card.passes import get_apple_pass_for_user

        attachment_filename = f"lv_apple_pass-{current_user.last_name.lower()}.pkpass"
        pkpass_out_path = get_apple_pass_for_user(
            user=current_user,
        )
        return send_file(
            pkpass_out_path,
            attachment_filename=attachment_filename,
            mimetype="application/vnd.apple.pkpass",
            as_attachment=True,
        )
    return redirect(url_for("home"))


@app.route("/squarespace/oauth/login")
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
    from member_card.db import db
    from member_card.models import SquarespaceWebhook
    from member_card.pubsub import publish_message

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


@login_required
@app.route("/verify-pass/<serial_number>")
# Note: get_or_create_membership_card() has this route hard-coded in it
# TODO: ^ make that not the case
def verify_pass(serial_number):
    from member_card.db import db
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
    email_form_error_message = request.args.get("emailFormErrorMessage", "")
    return render_template(
        "login.html.j2",
        email_form_error_message=email_form_error_message,
        recaptcha_site_key=app.config["RECAPTCHA_SITE_KEY"],
    )


@login_required
@app.route("/logout")
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


@app.cli.command("sync-subscriptions")
@click.option("-l", "--load-all", default=False)
def sync_subscriptions(load_all):
    from member_card.worker import sync_subscriptions_etl

    etl_results = sync_subscriptions_etl(
        message=dict(type="cli-sync-subscriptions"),
        load_all=load_all,
    )
    logger.info(f"sync_subscriptions() => {etl_results=}")


@app.cli.command("sync-order-id")
@click.argument("order_id")
def sync_order_id(order_id):
    from member_card.worker import sync_squarespace_order

    sync_order_result = sync_squarespace_order(
        message=dict(order_id=order_id),
    )
    logger.info(f"sync_order_id() => {sync_order_result=}")


@app.cli.command("recreate-user")
@click.argument("email")
def recreate_user(email):
    from social_core.actions import do_disconnect
    from social_flask.utils import load_strategy

    from member_card.db import db, get_or_create
    from member_card.models import User
    from member_card.utils import associations

    user = User.query.filter_by(email=email).one()
    memberships = list(user.annual_memberships)
    user_associations = associations(user=user, strategy=load_strategy())
    for association in user_associations:
        with app.app_context():
            disconnect_resp = do_disconnect(
                backend=association.get_backend_instance(load_strategy()),
                user=user,
                association_id=association.id,
            )
            logger.info(f"{disconnect_resp=}")

    db.session.delete(user)
    db.session.commit()
    member_user = get_or_create(
        session=db.session,
        model=User,
        email=email,
    )
    member_user.memberships = memberships
    db.session.add(member_user)
    db.session.commit()
    logger.debug(f"{memberships=}")


@app.cli.command("update-sendgrid-template")
def update_sendgrid_template():
    from member_card.sendgrid import update_sendgrid_template

    update_sendgrid_template()


@app.cli.command("send-test-email")
@click.argument("email")
def send_test_email(email):
    from member_card.sendgrid import generate_and_send_email

    generate_and_send_email(
        user=User.query.filter_by(email=email).one(),
    )


@app.cli.command("generate-card-image")
@click.argument("email")
def generate_card_image(email):
    from member_card.image import generate_card_image
    from member_card.models.membership_card import get_or_create_membership_card

    user = User.query.filter_by(email=email).one()
    membership_card = get_or_create_membership_card(
        user=user,
    )
    output_path = app.config["BASE_DIR"]
    logger.info(f"Generating image of {membership_card=} for {user=} to {output_path=}")
    generate_card_image(
        membership_card=membership_card,
        output_path=output_path,
    )


@app.cli.command("query-db")
@click.argument("email")
def query_db(email):
    from member_card.models import AnnualMembership

    memberships = (
        AnnualMembership.query.filter_by(customer_email=func.lower(email))
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )

    logger.info(f"memberships matching {email}:\n{memberships}")
    user = User.query.filter_by(email=func.lower(email)).one()
    logger.info(f"user matching {email}:\n{user}")
    logger.info(f"user roles {email}:\n{user.roles}")
    logger.info(f"user memberships:\n{user.annual_memberships}")
    logger.info(f"user membership cards:\n{user.membership_cards}")


@app.cli.command("query-order-num")
@click.argument("order_num")
def query_order_num(order_num):
    from member_card.models import AnnualMembership

    memberships = (
        AnnualMembership.query.filter_by(order_number=order_num)
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )

    logger.info(f"memberships matching {order_num}:\n{memberships}")
    users = [m.user for m in memberships]
    logger.info(f"user matching {order_num}:\n{users}")
    for user in users:
        logger.info(f"user memberships:\n{user.annual_memberships}")
        logger.info(f"user membership cards:\n{user.membership_cards}")


@app.cli.command("create-apple-pass")
@click.argument("email")
@click.option("-z", "--zip-file-path")
def create_apple_pass_cli(email, zip_file_path=None):
    create_apple_pass(email=email, zip_file=zip_file_path)


def create_apple_pass(email, zip_file=None):
    pass


@app.cli.command("force-assets-bundle-build")
def force_assets_bundle_build():
    utils.force_assets_bundle_build(app)


@app.cli.command("upload-statics")
def upload_statics():
    from member_card.cloudbuild import create_upload_statics_build

    utils.force_assets_bundle_build(app)
    create_upload_statics_build()


@app.cli.command("build-image")
@click.argument("image_name")
def build_image(image_name):
    from member_card.cloudbuild import create_docker_image_build

    build_result = create_docker_image_build(image_name=image_name)
    print(f"::set-output name=image::{build_result.images[0]}")


@app.cli.command("insert-google-pass-class")
def insert_google_pass_class():
    from member_card import gpay

    class_id = app.config["GOOGLE_PAY_PASS_CLASS_ID"]
    pass_class_payload = gpay.GooglePayPassClass(class_id).to_dict()

    insert_class_response = gpay.new_client().insert_class(
        class_id=class_id,
        payload=pass_class_payload,
    )
    logger.debug(f"Class ID: {class_id} insert response: {insert_class_response=}")


@app.cli.command("update-google-pass-class")
def update_google_pass_class():
    from member_card import gpay

    class_id = app.config["GOOGLE_PAY_PASS_CLASS_ID"]
    pass_class_payload = gpay.GooglePayPassClass(class_id).to_dict()

    update_class_response = gpay.new_client().patch_class(
        class_id=class_id,
        payload=pass_class_payload,
    )
    logger.debug(f"Class ID: {class_id} update response: {update_class_response=}")


@app.cli.command("demo-google-pay-pass")
@click.argument("email")
def demo_google_pay_pass(email):
    from member_card import gpay
    from member_card.models.membership_card import get_or_create_membership_card

    SAVE_LINK = "https://pay.google.com/gp/v/save/"

    user = User.query.filter_by(email=email).one()
    membership_card = get_or_create_membership_card(
        user=user,
    )

    pass_jwt = gpay.generate_pass_jwt(
        membership_card=membership_card,
    )

    print(f"This is an 'object' jwt:\n{pass_jwt.decode('UTF-8')}\n")
    print(
        "you can decode it with a tool to see the unsigned JWT representation:\nhttps://jwt.io\n"
    )
    print(f"Try this save link in your browser:\n{SAVE_LINK}{pass_jwt.decode('UTF-8')}")


@app.cli.command("apple-serial-num-to-hex")
@click.argument("serial_num")
def apple_serial_num_to_hex(serial_num):
    from uuid import UUID

    print(UUID(int=int(serial_num)))


@app.cli.command("publish-sync-subscriptions-msg")
def publish_sync_subscriptions_msg():

    from member_card.pubsub import publish_message

    topic_id = app.config["GCLOUD_PUBSUB_TOPIC_ID"]
    logger.info(f"publishing sync_subscriptions_etl message to pubsub {topic_id=}")
    publish_message(
        project_id=app.config["GCLOUD_PROJECT"],
        topic_id=topic_id,
        message_data=dict(
            type="sync_subscriptions_etl",
        ),
    )


@app.cli.command("add-memberships-to-user-email")
@click.argument("order_email")
@click.argument("user_email")
def add_memberships_to_user_email(order_email, user_email):
    logger.debug(f"{order_email=} => {user_email=}")
    from member_card.db import db
    from member_card.models import AnnualMembership

    memberships = (
        AnnualMembership.query.filter_by(customer_email=order_email)
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )
    logger.debug(f"memberships matching {order_email}: {memberships}")

    user = User.query.filter_by(email=user_email).one()
    logger.debug(f"user returned for {user_email}: {user=}")
    logger.info(f"Adding memberships orders from {order_email} to: {user_email}")
    for membership in memberships:
        logger.debug(
            f"setting user_id attribute on {membership=} from {membership.user_id} to: {user.id}"
        )
        setattr(membership, "user_id", user.id)
        db.session.add(membership)
        db.session.commit()


@app.cli.command("update-user-name")
@click.argument("user_email")
@click.argument("first_name")
@click.argument("last_name")
def update_user_name(user_email, first_name, last_name):
    logger.debug(f"{user_email=} => {first_name=} {last_name=}")
    from member_card.db import db

    user = User.query.filter_by(email=func.lower(user_email)).one()
    logger.debug(f"user returned for {user_email}: {user=}")
    logger.info(
        f"Update name for {user} from {user.fullname} to: {first_name} {last_name}"
    )
    setattr(user, "fullname", " ".join([first_name, last_name]))
    setattr(user, "first_name", first_name)
    setattr(user, "last_name", last_name)
    db.session.add(user)
    db.session.commit()
    logger.debug(f"post-commit: {user=}")


@app.cli.command("add-role-to-user")
@click.argument("user_email")
@click.argument("role_name")
def add_role_to_user(user_email, role_name):
    from flask_security import SQLAlchemySessionUserDatastore

    from member_card.db import db
    from member_card.models.user import Role

    logger.debug(f"{user_email=} => {role_name=}")
    user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)

    user = user_datastore.get_user(user_email)
    admin_role = user_datastore.find_or_create_role(
        name="admin",
        description="Administrators allowed to connect Squarespace extensions, etc.",
    )
    db.session.add(admin_role)
    db.session.commit()
    logger.info(f"Adding {admin_role=} to user: {user=}")
    user_datastore.add_role_to_user(user=user, role=admin_role)
    logger.info(f"{admin_role=} successfully added for {user=}!")
    db.session.add(user)
    db.session.commit()
