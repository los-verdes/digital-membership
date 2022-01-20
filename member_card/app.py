#!/usr/bin/env python
import os

from flask import Flask, g, redirect, render_template
from flask_assets import Bundle, Environment
from flask_login import LoginManager, current_user, login_required, logout_user
from logzero import logger, setup_logger
from peewee import SqliteDatabase
from social_flask.routes import social_auth
from social_flask.template_filters import backends
from social_flask.utils import load_strategy
from social_flask_peewee.models import init_social
from webassets.filter import get_filter

from member_card.models.user import User, database_proxy
from member_card.utils import common_context

setup_logger(name=__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# App
app = Flask(__name__)
# app.config.from_object("member_card.settings")
libsass = get_filter(
    "libsass",
    as_output=True,
    style="compressed",
)
assets = Environment(app)  # create an Environment instance
bundles = {  # define nested Bundle
    "style": Bundle(
        "scss/*.scss",
        filters=(libsass),
        output="style.css",
    )
}
assets.register(bundles)

settings_path = os.getenv('DIGITAL_MEMBERSHIP_SETTINGS_PATH', "member_card.settings.Settings")
try:
    logger.debug(f"app.config before loading settings from object {settings_path}: {app.config=}")
    app.config.from_object(settings_path)
    logger.debug(f"app.config after loading settings from object {settings_path}: {app.config=}")
except ImportError as err:
    logger.exception(f"Unable to load settings from {settings_path}: {err=}")
    raise err

# DB
database = SqliteDatabase(app.config["DATABASE_URI"])
database_proxy.initialize(database)

app.register_blueprint(social_auth)
init_social(app, database)

login_manager = LoginManager()
# noqa
login_manager.login_view = "main"  # noqa
login_manager.login_message = ""
login_manager.init_app(app)


from social_flask import models

assert models
from social_flask import routes

assert routes


@login_manager.user_loader
def load_user(userid):
    try:
        return User.get(User.id == userid)
    except User.DoesNotExist:
        pass


@app.before_request
def global_user():
    # evaluate proxy value
    g.user = current_user._get_current_object()


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
def main():
    from logzero import logger

    from member_card.db import get_firestore_client
    from member_card.squarespace import AnnualMembership

    db = get_firestore_client()
    membership = None
    member_since_dt = None
    if current_user.is_authenticated:
        memberships_ref = db.collection("memberships")
        memberships = memberships_ref.where("email", "==", current_user.email)
        membership_objs = []
        member_since_dt = None
        for membership in memberships.stream():
            logger.info(f"{membership.id} => {membership.to_dict()}")
            m = AnnualMembership.from_dict(membership.to_dict())
            logger.info(f"{current_user.email} => {m=}")
            membership_objs.append(m)
        membership_objs = sorted(membership_objs, key=lambda m: m.created_on)
        membership = membership_objs[0]
        member_since_dt = membership_objs[-1].created_on

    return render_template(
        "home.html", membership=membership, member_since_dt=member_since_dt
    )


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


def create_app():
    from social_flask_peewee.models import FlaskStorage

    from member_card.models.user import User

    models = [
        User,
        FlaskStorage.user,
        FlaskStorage.nonce,
        FlaskStorage.association,
        FlaskStorage.code,
        FlaskStorage.partial,
    ]
    for model in models:
        model.create_table(True)
    return app
