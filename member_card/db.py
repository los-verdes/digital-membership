#!/usr/bin/env python
import logging

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
logger = logging.getLogger(__name__)


def get_or_update(session, model, filters, kwargs):
    filters = {f: kwargs[f] for f in filters if f in kwargs}
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    # for k, v in kwargs.items():
    #     logger.warning(f"{k} : {type(v)}")
    instance = session.query(model).filter_by(**filters).first()

    logger.debug(f"Getting or updatin' {model.__name__} matching {filters=}")
    if instance:
        for k, v in kwargs.items():
            setattr(instance, k, v)
        return instance
    else:
        instance = model(**kwargs)
        return instance


def get_or_create(session, model, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    # for k, v in kwargs.items():
    #     logger.warning(f"{k} : {type(v)}")
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        logger.debug(f"Creating {model.__name__} with {kwargs=}")
        instance = model(**kwargs)
        # session.add(instance)
        # session.commit()
        return instance
