#!/usr/bin/env python
import logging
from functools import partial
from typing import TYPE_CHECKING

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from google.cloud.sql.connector import connector

if TYPE_CHECKING:
    from pg8000 import dbapi

db = SQLAlchemy()
migrate = Migrate()
logger = logging.getLogger(__name__)


def get_gcp_sql_engine_creator(
    instance_connection_string, db_name, db_user, db_pass=None
):
    db_connection_kwargs = dict(
        instance_connection_string=instance_connection_string,
        db_user=db_user,
        db_name=db_name,
        db_pass=db_pass,
    )
    redacted_db_kwargs = {
        k: f"{v[:3]}...{v[-3:]}"
        for k, v in db_connection_kwargs.items()
        if v is not None
    }

    logger.debug(
        f"Using {redacted_db_kwargs} with GCP SQL cloud connector...",
        extra=redacted_db_kwargs,
    )

    def get_db_connector(
        instance_connection_string: str, db_user: str, db_name: str, db_pass: str
    ) -> "dbapi.Connection":
        conn_kwargs = dict(
            user=db_user,
            db=db_name,
            # enable_iam_auth=True,
        )

        conn_obj = connector.Connector()
        if db_pass:
            conn_kwargs["password"] = db_pass
        else:
            # TODO: drop this kludge pending release of https://github.com/GoogleCloudPlatform/cloud-sql-python-connector/pull/273
            conn_obj._enable_iam_auth = not db_pass
        conn: "dbapi.Connection" = conn_obj.connect(
            instance_connection_string,
            "pg8000",
            **conn_kwargs,
        )
        return conn

    engine_creator = partial(get_db_connector, **db_connection_kwargs)
    return engine_creator


def get_or_update(session, model, filters, kwargs):
    filters = {f: kwargs[f] for f in filters if f in kwargs}
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    instance = session.query(model).filter_by(**filters).first()

    logger.debug(f"Getting or updatin' {model.__name__} matching {filters=}")
    if instance:
        logger.debug(f"Updating existing instance: {instance=}")
        for k, v in kwargs.items():
            setattr(instance, k, v)
        return instance
    else:
        instance = model(**kwargs)
        logger.debug(f"New instance created!: {instance=}")
        return instance


def get_or_create(session, model, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    instance = session.query(model).filter_by(**kwargs).first()

    if instance:
        return instance
    else:
        logger.debug(f"Creating {model.__name__} with {kwargs=}")
        instance = model(**kwargs)
        return instance
