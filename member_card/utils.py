from social_core.backends.google import GooglePlusAuth
from social_core.backends.utils import load_backends

from member_card.settings import get_settings_obj_for_env

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


import uuid

# import pg8000
# import sqlalchemy
# from google.cloud.sql.connector import connector


def is_authenticated(user):
    if callable(user.is_authenticated):
        return user.is_authenticated()
    else:
        return user.is_authenticated


def associations(user, strategy):
    user_associations = strategy.storage.user.get_social_auth_for_user(user)
    if hasattr(user_associations, "all"):
        user_associations = user_associations.all()
    return list(user_associations)


def common_context(authentication_backends, strategy, user=None, plus_id=None, **extra):
    """Common view context"""
    context = {
        "user": user,
        "available_backends": load_backends(authentication_backends),
        "associated": {},
    }

    if user and is_authenticated(user):
        context["associated"] = dict(
            (association.provider, association)
            for association in associations(user, strategy)
        )

    if plus_id:
        context["plus_id"] = plus_id
        context["plus_scope"] = " ".join(GooglePlusAuth.DEFAULT_SCOPE)

    return dict(context, **extra)


table_name = f"books_{uuid.uuid4().hex}"


# [START cloud_sql_connector_postgres_pg8000]
# The Cloud SQL Python Connector can be used along with SQLAlchemy using the
# 'creator' argument to 'create_engine'
# def init_connection_engine() -> 'sqlalchemy.engine.Engine':
# def init_connection_engine():
#     def getconn() -> pg8000.dbapi.Connection:
#         settings = get_settings_obj_for_env()()
#         # breakpoint()
#         conn: pg8000.dbapi.Connection = connector.connect(
#             settings.POSTGRES_CONNECTION_NAME,
#             "pg8000",
#             # user="jeff.hogan1@gmail.com"
#             # user="website@lv-digital-membership.iam.gserviceaccount.com",  # settings.POSTGRES_USER,
#             user=settings.POSTGRES_USER,
#             password=settings.POSTGRES_PASS,
#             db=settings.POSTGRES_DB,
#             # enable_iam_auth=True,
#         )
#         return conn

#     engine = sqlalchemy.create_engine(
#         "postgresql+pg8000://",
#         creator=getconn,
#     )
#     engine.dialect.description_encoding = None
#     return engine


def get_db_engine(settings_obj):
    engine = create_engine(settings_obj.SQLALCHEMY_DATABASE_URI)
    return engine


def get_db_session(settings_obj=None):
    if settings_obj is None:
        settings_obj = get_settings_obj_for_env()
    engine = get_db_engine(settings_obj)
    # engine = init_connection_engine()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = scoped_session(Session)
    return db_session
