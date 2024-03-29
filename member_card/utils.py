import hashlib
import hmac
import logging
import uuid
from base64 import urlsafe_b64encode as b64e

import flask
from flask_assets import Bundle, Environment
from flask_login import LoginManager
from social_core.backends.google import GooglePlusAuth
from social_core.backends.utils import load_backends
from social_core.pipeline.user import get_username as social_get_username
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from webassets.filter import get_filter

from member_card.settings import get_settings_obj_for_env


class MembershipLoginManager(LoginManager):
    def __init__(self, app=None, add_context_processor=True):
        super().__init__(app, add_context_processor)
        self.login_view = "login"  # members_card.__name__


def get_username(strategy, details, user=None, *args, **kwargs):
    result = social_get_username(strategy, details, user=user, *args, **kwargs)
    if not result["username"]:
        result["username"] = getattr(user, "email")
    return result


def get_signing_key():
    signing_key = flask.current_app.config["SECRET_KEY"] * 5
    signing_key = signing_key.encode()
    return signing_key


def sign(data: str, algorithm=hashlib.sha256, key=None, use_hex_digest=False) -> str:
    if key is None:
        key = get_signing_key()
    assert len(key) >= algorithm().digest_size, (
        "Key must be at least as long as the digest size of the " "hashing algorithm"
    )
    if isinstance(data, str):
        data = data.encode()
    encoded_hmac = hmac.new(key, data, algorithm)
    if use_hex_digest:
        signed_digest = encoded_hmac.hexdigest().upper()
    else:
        signed_digest = encoded_hmac.digest()
        # we base64 encode things here for reasons (apple auth token verification... needs to be rethunk)
        signed_digest = b64e(signed_digest).decode()
    return signed_digest


def verify(signature: str, data: str, algorithm=hashlib.sha256, key=None) -> bool:
    expected = sign(data, algorithm, key=key)
    logging.debug(f"{signature=}")
    logging.debug(f"{expected=}")
    return hmac.compare_digest(expected, signature)


def verify_hex_digest(
    signature: str, data: str, algorithm=hashlib.sha256, key=None
) -> bool:
    expected = sign(data, algorithm, key=key, use_hex_digest=True)
    logging.debug(f"{signature=}")
    logging.debug(f"{expected=}")
    return hmac.compare_digest(expected, signature)


def load_settings(app, env=None):
    if env is None:
        logging.debug(f"{app.config['ENV']=}")
        env = app.config["ENV"].lower().strip()

    settings_obj = get_settings_obj_for_env(env)
    app.config.from_object(settings_obj())


libsass = get_filter(
    "libsass",
    as_output=True,
    style="compressed",
)


def force_assets_bundle_build(app):
    bundles = register_asset_bundles(app)
    for bundle_name, bundle in bundles.items():
        logging.info(f"Building bundle {bundle_name} ({bundle=})...")
        bundle.build(force=True, disable_cache=True)


def register_asset_bundles(app):
    assets = Environment(app)  # create an Environment instance
    bundles = {  # define nested Bundle
        "style": Bundle(
            "scss/*.scss",
            filters=(libsass),
            output="style.css",
        )
    }
    assets.register(bundles)

    return bundles


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


def get_db_engine(database_uri):
    engine = create_engine(database_uri)
    return engine


def get_db_session(database_uri):
    engine = get_db_engine(database_uri)
    # engine = init_connection_engine()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = scoped_session(Session)
    return db_session


# Reference: https://github.com/python-social-auth/social-examples/blob/02e42dd616f80510aaccb278374b686ee8dee2da/example-common/utils.py#L38
def social_url_for(name, **kwargs):
    if name == "social:begin":
        url = "/login/{backend}/"
    elif name == "social:complete":
        url = "/complete/{backend}/"
    elif name == "social:disconnect":
        url = "/disconnect/{backend}/"
    elif name == "social:disconnect_individual":
        url = "/disconnect/{backend}/{association_id}/"
    else:
        url = name
    # logging.debug(f"social_url_for() => {name=}: {kwargs=}")
    return url.format(**kwargs)


def get_jinja_template(template_path):
    from jinja2 import Environment, PackageLoader, select_autoescape

    env = Environment(
        loader=PackageLoader(__name__),
        autoescape=select_autoescape(),
    )
    return env.get_template(template_path)


def get_message_str(message_key):
    message_str = flask.current_app.config["MESSAGES"][message_key]
    return message_str
