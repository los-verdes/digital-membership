#!/usr/bin/env python
import json
import os
from datetime import datetime

import click
from flask import (Flask, g, redirect, render_template, request, send_file,
                   url_for)
from flask.logging import default_handler
from flask_gravatar import Gravatar
from flask_login import current_user as current_login_user
from flask_login import login_required, logout_user
from flask_recaptcha import ReCaptcha
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from social_flask.template_filters import backends
from social_flask.utils import load_strategy

from member_card import utils
from member_card.db import squarespace_orders_etl
from member_card.models import User
from member_card.squarespace import Squarespace

BASE_DIR = os.path.dirname(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "member_card")
)


app = Flask(__name__)
logger = app.logger
logger.propagate = False

login_manager = utils.MembershipLoginManager()

recaptcha = ReCaptcha()


def create_app():
    utils.load_settings(app)

    logger.debug("initialize_tracer")
    if app.config["TRACING_ENABLED"]:
        utils.initialize_tracer()

    # utils.configure_logging(
    #     project_id=app.config["GCLOUD_PROJECT"],
    #     # running_in_cloudrun=running_in_cloudrun
    # )
    app.logger.removeHandler(default_handler)

    # log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper())
    # app.logger.setLevel(log_level)
    # app.logger.propagate = True

    logger.debug("instrument_app")
    FlaskInstrumentor().instrument_app(app)

    logger.debug("register_asset_bundles")
    utils.register_asset_bundles(app)

    logger.debug("login_manager.init_app")
    login_manager.init_app(app)

    from member_card.db import db

    db.init_app(app)

    from social_flask.routes import social_auth

    app.register_blueprint(social_auth)

    from social_flask_sqlalchemy.models import init_social

    init_social(app, db.session)

    with app.app_context():
        db.create_all()

    from member_card.routes import passkit

    assert passkit

    gravatar = Gravatar(
        app,
        size=100,
        rating="g",
        default="retro",
        force_default=False,
        force_lower=False,
        use_ssl=True,
        base_url=None,
    )
    assert gravatar

    recaptcha.init_app(app)

    # with app.app_context():
    #     app.config.update(
    #         dict(
    #             SOCIAL_AUTH_LOGIN_URL=url_for("login"),
    #             SOCIAL_AUTH_LOGIN_REDIRECT_URL=url_for("home"),
    #         )
    #     )
    return app


@login_manager.user_loader
def load_user(userid):
    try:
        return User.query.get(int(userid))
    except (TypeError, ValueError):
        pass


@app.before_request
def global_user():
    # evaluate proxy value
    g.user = current_login_user._get_current_object()


@app.teardown_appcontext
def commit_on_success(error=None):
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
    from member_card.db import get_membership_table_last_sync

    return utils.common_context(
        app.config["SOCIAL_AUTH_AUTHENTICATION_BACKENDS"],
        load_strategy(),
        getattr(g, "user", None),
        app.config.get("SOCIAL_AUTH_GOOGLE_PLUS_KEY"),
        membership_last_sync=get_membership_table_last_sync(),
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
        from member_card.passes import get_or_create_membership_card

        membership_card = get_or_create_membership_card(current_user)
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
        )


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
        email_distribution_recipient=email_distribution_recipient,
        submission_response_msg="Request received",
        redirect_home_delay_seconds="45",
    )


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


@login_required
@app.route("/verify-pass/<serial_number>")
def verify_pass(serial_number):
    from member_card.db import db
    from member_card.models import AnnualMembership, MembershipCard

    signature = request.args.get("signature")
    if not signature:
        return "Unable to verify signature!", 401

    signature_verified = utils.verify(signature=signature, data=serial_number)
    if not signature_verified:
        return "Unable to verify signature!", 401
    # current_user = g.user
    # if current_user.is_authenticated:
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


@app.route("/pubsub", methods=["POST"])
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


@app.cli.command("ensure-db-schemas")
@click.option("-D", "--drop-first", default=False)
def ensure_db_schemas(drop_first):
    logger.debug("ensure-db-schemas: calling `db.create_all()`")
    from member_card.db import ensure_db_schemas

    ensure_db_schemas(drop_first)


@app.cli.command("sync-subscriptions")
@click.option("-m", "--membership-sku", default="SQ3671268")
@click.option("-l", "--load-all", default=False)
def sync_subscriptions(membership_sku, load_all):
    from member_card.db import db

    squarespace = Squarespace(api_key=app.config["SQUARESPACE_API_KEY"])
    etl_results = squarespace_orders_etl(
        squarespace_client=squarespace,
        db_session=db.session,
        membership_sku=membership_sku,
        load_all=load_all,
    )
    logger.info(f"sync_subscriptions() => {etl_results=}")


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
    # for membership_card in user.membership_cards:
    #     for apple_device_registration in membership_card.apple_device_registrations:
    #         db.session.delete(apple_device_registration)
    #     db.session.delete(membership_card)
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
    from sendgrid import SendGridAPIClient

    sg = SendGridAPIClient(app.config["SENDGRID_API_KEY"])
    template_id = app.config["SENDGRID_TEMPLATE_ID"]
    get_template_resp = sg.client.templates._(template_id).get()
    template = json.loads(get_template_resp.body.decode())
    version = template["versions"][0]
    version_id = version["id"]
    from jinja2 import Environment, PackageLoader, select_autoescape

    env = Environment(
        loader=PackageLoader(__name__),
        autoescape=select_autoescape(),
        variable_start_string="{~~ ",
        variable_end_string=" ~~}",
        comment_start_string="{#~",
        comment_end_string="~#}",
    )
    html_template = env.get_template("sendgrid_email.html.j2")
    updated_html_content = html_template.render(
        preview_text="Your requested Los Verdes membership card details are attached! PNG image, Apple Wallet and Google Play pass formats enclosed. =D",
        view_online_href="https://card.losverd.es",
        logo_src="card.losverd.es/static/LosVerdes_Logo_RGB_300_Horizontal_VerdeOnTransparent_CityYear.png",
        downloads_img_src="card.losverd.es/static/small_lv_hands.png",
        footer_logo_src="card.losverd.es/static/lv_hands.png",
        card_img_src="{{cardImageUrl}}",
    )
    version["html_content"] = updated_html_content.strip()

    plain_template = env.get_template("sendgrid_email.txt")
    updated_plain_content = plain_template.render(
        preview_text="Your requested Los Verdes membership card details are attached! PNG image, Apple Wallet and Google Play pass formats enclosed. =D",
        view_online_href="https://card.losverd.es",
        logo_src="card.losverd.es/static/LosVerdes_Logo_RGB_300_Horizontal_VerdeOnTransparent_CityYear.png",
        downloads_img_src="card.losverd.es/static/small_lv_hands.png",
        footer_logo_src="card.losverd.es/static/lv_hands.png",
        card_img_src="{{cardImageUrl}}",
    )
    version["plain_content"] = updated_plain_content.strip()

    # PATCH Response: 400 b'{"error":"You cannot switch editors once a dynamic template version has been created."}\n'
    del version["editor"]
    # breakpoint()
    patch_version_resp = (
        sg.client.templates._(template_id)
        .versions._(version_id)
        .patch(request_body=version)
    )

    logger.debug(f"{patch_version_resp.status_code=}:: {patch_version_resp.headers=}")
    logger.info(f"{json.loads(patch_version_resp.body.decode())}")


@app.cli.command("send-test-email")
@click.argument("email")
@click.argument("base_url", default="https://card.losverd.es")
def send_test_email(email, base_url):
    from member_card.sendgrid import generate_and_send_email

    generate_and_send_email(
        user=User.query.filter_by(email=email).one(),
    )


@app.cli.command("query-db")
@click.argument("email")
def query_db(email):
    from member_card.models import AnnualMembership

    memberships = (
        AnnualMembership.query.filter_by(customer_email=email)
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )
    member_name = None
    member_since_dt = None
    if memberships:
        member_since_dt = memberships[-1].created_on
        member_name = memberships[-1].full_name
    logger.debug(f"{member_name=} => {member_since_dt=}")
    logger.debug(f"{memberships=}")


@app.cli.command("create-apple-pass")
@click.argument("email")
@click.option("-z", "--zip-file-path")
def create_apple_pass_cli(email, zip_file_path=None):
    create_apple_pass(email=email, zip_file=zip_file_path)


def create_apple_pass(email, zip_file=None):
    pass
