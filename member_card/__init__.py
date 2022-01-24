#!/usr/bin/env python
import os
import click
from flask import Flask, g, redirect, render_template, send_file, url_for
from flask_login import current_user as current_login_user
from flask_login import login_required, logout_user
from logzero import logger, setup_logger
from social_flask.template_filters import backends
from social_flask.utils import load_strategy
import tempfile
from member_card.db import db
from member_card.models import User
from member_card import utils

BASE_DIR = os.path.dirname(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "member_card")
)
setup_logger(name=__name__)

# App
app = Flask(__name__)
utils.load_settings(app)
utils.register_asset_bundles(app)
db_session = utils.init_social_auth(app)
login_manager = utils.init_login_manager(app)

db.init_app(app)


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
    if error is None:
        db_session.commit()
    else:
        db_session.rollback()

    db_session.remove()


@app.context_processor
def inject_user():
    try:
        return {"user": g.user}
    except AttributeError:
        return {"user": None}


@app.context_processor
def load_common_context():
    return utils.common_context(
        app.config["SOCIAL_AUTH_AUTHENTICATION_BACKENDS"],
        load_strategy(),
        getattr(g, "user", None),
        app.config.get("SOCIAL_AUTH_GOOGLE_PLUS_KEY"),
    )


app.context_processor(backends)


@login_required
@app.route("/")
def home():
    from logzero import logger

    from member_card.models import AnnualMembership

    current_user = g.user
    membership_table_keys = list(AnnualMembership().to_dict().keys())
    if current_user.is_authenticated:
        logger.debug(f"filter: customer_email={current_user.email=}")
        if customer_email := current_user.email:
            memberships = (
                AnnualMembership.query.filter_by(customer_email=customer_email)
                .order_by(AnnualMembership.created_on.desc())
                .all()
            )
            member_name = None
            member_since_dt = None
            member_expiry_dt = None
            if memberships:
                member_since_dt = memberships[-1].created_on
                member_name = memberships[-1].full_name
                member_expiry_dt = memberships[0].expiry_date
            return render_template(
                "home.html",
                member_name=member_name,
                membership_table_keys=membership_table_keys,
                memberships=memberships,
                member_since_dt=member_since_dt,
                member_expiry_dt=member_expiry_dt,
            )
    return render_template(
        "home.html",
    )


@login_required
@app.route("/passes/apple-pay")
def passes_apple_pay():
    current_user = g.user
    if current_user.is_authenticated:
        attachment_filename = f"lv_apple_pass-{current_user.last_name.lower()}.pkpass"
        _, filepath = tempfile.mkstemp()
        create_apple_pass(current_user.email, filepath)
        return send_file(
            filepath, attachment_filename=attachment_filename, as_attachment=True
        )
    return redirect(url_for('home'))


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


@app.cli.command("syncdb")
def ensure_db_schema():
    # from social_flask_sqlalchemy import models

    # from member_card.models import user

    logger.debug("syncdb: calling `db.create_all()`")
    # metadata = MetaData()
    # metadata.create_all()
    # db.create_all()
    from social_flask_sqlalchemy import models as social_flask_models

    from member_card import models
    from utils import create_engine

    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    models.User.metadata.create_all(engine)
    models.TableMetadata.metadata.create_all(engine)
    models.AnnualMembership.metadata.create_all(engine)
    social_flask_models.PSABase.metadata.create_all(engine)


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
    from member_card.models import AnnualMembership
    from wallet.models import Pass, Barcode, Generic, BarcodeFormat

    memberships = (
        AnnualMembership.query.filter_by(customer_email=email)
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )
    if not memberships:
        raise Exception(f"No matching memberships found for {email=}")
    member_since_dt = memberships[-1].created_on
    member_name = memberships[-1].full_name
    member_expiry_dt = memberships[0].expiry_date
    cardInfo = Generic()
    cardInfo.addPrimaryField("name", member_name, "Member Name")
    cardInfo.addSecondaryField(
        "member_since", member_since_dt.strftime("%b %Y"), "Member Since"
    )
    # cardInfo.addSecondaryField(
    #     "member_expiry", member_expiry_dt.strftime("%b %d, %Y"), "Good through"
    # )
    # cardInfo.addPrimaryField("member_expiry", member_expiry_dt.strftime("%b %Y"), "Good through")

    # cardInfo.addHeaderField(key="test_header", value="Testing the header", label="Test Header")
    # cardInfo.addHeaderField(key="test_aux", value="Testing the aux", label="Test Aux")
    logger.debug(f"{str(member_expiry_dt.strftime('%b %d, %Y'))=}")
    cardInfo.addBackField(
        "member_expiry_back",
        member_expiry_dt.strftime("%b %d, %Y"),
        "Good through",
    )
    # cardInfo.addBackField("hmm", "Hi there", "Hullo")
    # cardInfo.addBackField(key="test_back", value="Testing the back", label="Test Back")

    organizationName = app.config["APPLE_DEVELOPER_TEAM_ID"]
    passTypeIdentifier = app.config["APPLE_DEVELOPER_PASS_TYPE_ID"]
    teamIdentifier = app.config["APPLE_DEVELOPER_TEAM_ID"]

    passfile = Pass(
        cardInfo,
        passTypeIdentifier=passTypeIdentifier,
        organizationName=organizationName,
        teamIdentifier=teamIdentifier,
    )
    logo_text = "Membership Card"
    serial_number = "1234567"
    qr_code = Barcode(format=BarcodeFormat.QR, message="Barcode message")
    passfile_attrs = dict(
        serialNumber=serial_number,
        backgroundColor="rgb(0, 177, 64)",
        foregroundColor="rgb(0, 0, 0)",
        logoText=logo_text,
        barcode=qr_code,
    )
    for attr_name, attr_value in passfile_attrs.items():
        setattr(
            passfile,
            attr_name,
            attr_value,
        )

    # Including the icon and logo is necessary for the passbook to be valid.
    static_dir = os.path.join(BASE_DIR, "static")
    passfile_files = {
        "icon.png": "LV_Tee_Crest_onVerde_rgb_filled_icon.png",
        "icon@2x.png": "LV_Tee_Crest_onVerde_rgb_filled_icon@2x.png",
        "logo.png": "LosVerdes_Logo_RGB_72_Horizontal_BlackOnTransparent_CityYear_logo.png",
        "logo@2x.png": "LosVerdes_Logo_RGB_300_Horizontal_BlackOnTransparent_CityYear_logo@2x.png",
    }
    for passfile_filename, local_filename in passfile_files.items():
        file_path = os.path.join(static_dir, local_filename)
        passfile.addFile(passfile_filename, open(file_path, "rb"))

    # Create and output the Passbook file (.pkpass)

    cert_fp = tempfile.NamedTemporaryFile(mode="w", suffix=".pem")
    cert_fp.write("\n".join(app.config["APPLE_DEVELOPER_CERTIFICATE"].split("\\n")))
    cert_fp.seek(0)
    key_fp = tempfile.NamedTemporaryFile(mode="w", suffix=".key")
    key_fp.write("\n".join(app.config["APPLE_DEVELOPER_PRIVATE_KEY"].split("\\n")))
    key_fp.seek(0)
    password = app.config["APPLE_DEVELOPER_PRIVATE_KEY_PASSWORD"]
    cert_filepath = cert_fp.name
    key_filepath = key_fp.name
    logger.debug(f"{cert_filepath=}")
    logger.debug(f"{key_filepath=}")
    new_passfile = passfile.create(
        certificate=cert_filepath,
        key=key_filepath,
        wwdr_certificate=os.path.join(BASE_DIR, "wwdr.pem"),
        password=password,
        zip_file=zip_file,  # os.path.join(secrets_dir, "test.pkpass"),
    )
    cert_fp.close()
    key_fp.close()
    return new_passfile
