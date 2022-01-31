#!/usr/bin/env python
import os
from urllib.parse import urlparse

import click
from flask import Flask, g, redirect, render_template, request, send_file, url_for
from flask.logging import default_handler
from flask_gravatar import Gravatar
from flask_login import current_user as current_login_user
from flask_login import login_required, logout_user
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


def get_base_url():
    parsed_base_url = urlparse(request.base_url)
    # return f"{parsed_base_url.scheme}://{parsed_base_url.netloc}"
    return f"https://{parsed_base_url.netloc}"


def create_app():
    utils.load_settings(app)

    if app.config["TRACING_ENABLED"]:
        utils.initialize_tracer()

    # utils.configure_logging(
    #     project_id=app.config["GCLOUD_PROJECT"],
    #     # running_in_cloudrun=running_in_cloudrun
    # )
    app.logger.removeHandler(default_handler)
    # app.logger.propagate = True

    FlaskInstrumentor().instrument_app(app)

    utils.register_asset_bundles(app)
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

    # return redirect(url_for("home"))


@app.route("/privacy-policy")
def privacy_policy():
    return render_template(
        "privacy_policy.html.j2",
    )


# @login_required
# @app.route("/done/")
# def done():
#     return render_template("home2.html.j2")


@app.route("/login")
def login():
    """Logout view"""
    return render_template("login.html.j2")


@login_required
@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")


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
