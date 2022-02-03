#!/usr/bin/env python
import logging

from flask.logging import default_handler
from flask_gravatar import Gravatar
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from member_card import utils


def create_cli_app():
    from member_card.app import app

    utils.load_settings(app)
    return app


def create_app():
    from member_card.app import login_manager, recaptcha, cdn

    logger = logging.getLogger(__name__)

    app = create_cli_app()

    logger.debug("cdn.init_app")
    cdn.init_app(app)

    logger.debug("initialize_tracer")
    if app.config["TRACING_ENABLED"]:
        utils.initialize_tracer()

    app.logger.removeHandler(default_handler)

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
