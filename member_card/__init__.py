#!/usr/bin/env python
import logging
import os
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from flask_security import SQLAlchemySessionUserDatastore
from flask.logging import default_handler
from flask_gravatar import Gravatar
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from member_card import utils


def initialize_tracer():
    set_global_textmap(CloudTraceFormatPropagator())
    tracer_provider = TracerProvider()
    cloud_trace_exporter = CloudTraceSpanExporter()
    tracer_provider.add_span_processor(
        # BatchSpanProcessor buffers spans and sends them in batches in a
        # background thread. The default parameters are sensible, but can be
        # tweaked to optimize your performance
        BatchSpanProcessor(cloud_trace_exporter)
    )
    trace.set_tracer_provider(tracer_provider)


def create_cli_app(env=None):
    from member_card.app import app

    logger = logging.getLogger(__name__)

    logger.debug("load_settings")
    utils.load_settings(app, env)

    logger.debug("register_asset_bundles")
    utils.register_asset_bundles(app)

    from member_card import commands

    assert commands

    return app


class MemberCardDatastore(SQLAlchemySessionUserDatastore):
    def find_user(self, **kwargs):
        if "id" in kwargs:
            kwargs["id"] = int(kwargs["id"])
        return self.user_model.query.filter_by(**kwargs).first()


def create_app(env=None):
    from member_card.app import login_manager, recaptcha, cdn, security

    logger = logging.getLogger(__name__)

    app = create_cli_app(env)

    if os.getenv("K_SERVICE") == "worker":
        from member_card.worker import worker_bp

        logger.debug("registering worker blueprint")
        app.register_blueprint(worker_bp)

    logger.debug("cdn.init_app")
    cdn.init_app(app)

    logger.debug("initialize_tracer")
    if app.config["TRACING_ENABLED"]:
        initialize_tracer()

    app.logger.removeHandler(default_handler)

    logger.debug("instrument_app")
    FlaskInstrumentor().instrument_app(app)

    logger.debug("login_manager.init_app")
    login_manager.init_app(app)

    from social_flask_sqlalchemy.models import init_social
    from member_card.db import db, migrate

    db.init_app(app)
    init_social(app, db.session)
    migrate.init_app(app, db)

    from member_card.models.user import User, Role

    user_datastore = MemberCardDatastore(db.session, User, Role)
    security.init_app(
        app=app,
        datastore=user_datastore,
    )

    from social_flask.routes import social_auth

    app.register_blueprint(social_auth)

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

    return app
