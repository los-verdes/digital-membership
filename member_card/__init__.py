#!/usr/bin/env python
import os

from flask import Flask, g, redirect, render_template
from flask_login import current_user as current_login_user
from flask_login import login_required, logout_user
from logzero import logger, setup_logger
from social_flask.template_filters import backends
from social_flask.utils import load_strategy

from member_card.db import db
from member_card.models import User
from member_card import utils

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
def main():
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
                member_expiry_dt = memberships[-1].expiry_date
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


# def create_app():
#     from member_card.models.user import User

#     models = [
#         User,
#         FlaskStorage.user,
#         FlaskStorage.nonce,
#         FlaskStorage.association,
#         FlaskStorage.code,
#         FlaskStorage.partial,
#     ]
#     for model in models:
#         model.create_table(True)
#     return app
