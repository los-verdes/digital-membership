#!/usr/bin/env python
import os

import click
from flask import Flask, g, redirect, render_template, request, send_file, url_for
from flask_login import current_user as current_login_user
from flask_login import login_required, logout_user
from logzero import logger, setup_logger
from social_flask.template_filters import backends
from social_flask.utils import load_strategy

from member_card.db import squarespace_orders_etl
from member_card.models import User
from member_card.squarespace import Squarespace
from member_card.utils import (
    MembershipLoginManager,
    common_context,
    load_settings,
    register_asset_bundles,
    verify,
)

BASE_DIR = os.path.dirname(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "member_card")
)

setup_logger(name=__name__)

app = Flask(__name__)
login_manager = MembershipLoginManager()


def create_app():
    load_settings(app)
    register_asset_bundles(app)
    login_manager.init_app(app)

    from member_card.db import db

    db.init_app(app)

    from social_flask.routes import social_auth
    from social_flask_sqlalchemy.models import init_social

    app.register_blueprint(social_auth)
    init_social(app, db.session)

    with app.app_context():
        db.create_all()

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
    return common_context(
        app.config["SOCIAL_AUTH_AUTHENTICATION_BACKENDS"],
        load_strategy(),
        getattr(g, "user", None),
        app.config.get("SOCIAL_AUTH_GOOGLE_PLUS_KEY"),
    )


app.context_processor(backends)


@login_required
@app.route("/")
def home():
    from member_card.models import AnnualMembership

    return render_template(
        "home.html",
        # member=g.user,
        membership_card=g.user.latest_membership_card,
        membership_orders=g.user.annual_memberships,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
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
            base_url=request.base_url,
            # organization_name=app.config["APPLE_DEVELOPER_TEAM_ID"],
            # pass_type_identifier=app.config["APPLE_DEVELOPER_PASS_TYPE_ID"],
            # team_identifier=app.config["APPLE_DEVELOPER_TEAM_ID"],
        )
        return send_file(
            pkpass_out_path, attachment_filename=attachment_filename, as_attachment=True
        )
    return redirect(url_for("home"))


@login_required
@app.route("/passes/apple-pay/verify/<serial_number>")
def verify_apple_pay_pass(serial_number):
    from member_card.db import db
    from member_card.models import MembershipCard, AnnualMembership

    signature = request.args.get("signature")
    if not signature:
        return "Unable to verify signature!", 401

    signature_verified = verify(signature=signature, data=serial_number)
    if not signature_verified:
        return "Unable to verify signature!", 401
    # current_user = g.user
    # if current_user.is_authenticated:
    card_to_verify = (
        db.session.query(MembershipCard).filter_by(serial_number=serial_number).one()
    )
    logger.debug(f"{card_to_verify=}")

    return render_template(
        "home.html",
        # member=g.user,
        membership_card=card_to_verify,
        membership_orders=card_to_verify.user.annual_memberships,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
    )

    # return redirect(url_for("home"))


@app.route("/privacy-policy")
def privacy_policy():
    return render_template(
        "privacy_policy.html",
    )


# @login_required
# @app.route("/done/")
# def done():
#     return render_template("home2.html")


@login_required
@app.route("/logout/")
def logout():
    """Logout view"""
    logout_user()
    return redirect("/")


@app.cli.command("ensure-db-schemas")
def ensure_db_schemas():
    # from social_flask_sqlalchemy import models

    # from member_card.models import user

    logger.debug("ensure-db-schemas: calling `db.create_all()`")
    # metadata = MetaData()
    # metadata.create_all()
    # db.create_all()
    from social_flask_sqlalchemy import models as social_flask_models

    from member_card import models
    from member_card.db import db

    engine = db.engine
    # engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    models.User.metadata.create_all(engine)
    models.TableMetadata.metadata.create_all(engine)
    models.AnnualMembership.metadata.create_all(engine)
    models.MembershipCard.metadata.create_all(engine)
    social_flask_models.PSABase.metadata.create_all(engine)


@app.cli.command("populate-db")
@click.option("-m", "--membership-sku", default="SQ3671268")
@click.option("-l", "--load-all", default=False)
def populate_db(membership_sku, load_all):
    from member_card.db import db

    squarespace = Squarespace(api_key=os.environ["SQUARESPACE_API_KEY"])
    etl_results = squarespace_orders_etl(
        squarespace_client=squarespace,
        db_session=db.session,
        membership_sku=membership_sku,
        load_all=load_all,
    )
    logger.debug(f"{etl_results=}")


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
