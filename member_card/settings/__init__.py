import json
import os
from functools import partial
from os.path import abspath, dirname, join
from typing import TYPE_CHECKING

from google.cloud.sql.connector import connector
from logzero import logger

if TYPE_CHECKING:
    from pg8000 import dbapi


class Settings(object):
    _secrets = dict()

    def export_dict_as_settings(self, dict_to_export):
        for key, value in dict_to_export.items():
            settings_key = key.upper()
            logger.debug(f"Exporting {key} as settings key: {settings_key}")
            setattr(self, settings_key, value)

    def export_secrets_as_settings(self):
        logger.debug(f"Exporting {list(self._secrets.keys())} as setting attributes...")
        self.export_dict_as_settings(self._secrets)

    def use_gcp_sql_connector(self):
        db_connection_kwargs = dict(
            instance_connection_string=self.DB_CONNECTION_NAME,
            db_user=self.DB_USERNAME,
            db_name=self.DB_DATABASE_NAME,
        )

        logger.debug(f"{db_connection_kwargs=}")

        def get_db_connector(
            instance_connection_string, db_user, db_name
        ) -> "dbapi.Connection":
            conn: "dbapi.Connection" = connector.connect(
                instance_connection_string,
                "pg8000",
                # ip_type=instance_connection_manager.IPTypes.PRIVATE,
                user=db_user,
                db=db_name,
                enable_iam_auth=True,
            )
            return conn

        engine_creator = partial(get_db_connector, **db_connection_kwargs)
        self.SQLALCHEMY_ENGINE_OPTIONS = dict(
            creator=engine_creator,
        )

    def __init__(self) -> None:
        logger.debug(f"Initializing settings class: {type(self)}...")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

    APPLE_DEVELOPER_ORG_NAME = "Jeffrey Hogan"  # TODO: if LV is a legit 501c this can maybe become a less personal org...
    APPLE_DEVELOPER_PASS_TYPE_ID = "pass.es.losverd.card"
    APPLE_DEVELOPER_TEAM_ID = "KJHZP635V9"

    APPLE_DEVELOPER_CERTIFICATE = os.environ.get("APPLE_DEVELOPER_CERTIFICATE", None)
    APPLE_DEVELOPER_PRIVATE_KEY = os.environ.get("APPLE_DEVELOPER_PRIVATE_KEY", None)
    APPLE_DEVELOPER_PRIVATE_KEY_PASSWORD = os.environ.get(
        "APPLE_DEVELOPER_PRIVATE_KEY_PASSWORD", None
    )

    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get("GOOGLE_CLIENT_ID", None)
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = os.getenv("GOOGLE_OAUTH2_SCOPE", [])
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

    # from: https://github.com/python-social-auth/social-examples
    SECRET_KEY = os.environ.get("SECRET_KEY", "not-very-secret-at-all")
    SESSION_COOKIE_NAME = "psa_session"
    DEBUG = True
    DATABASE_URI = "%s/db.sqlite3" % dirname(abspath(join(__file__, "..")))
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    SESSION_PROTECTION = "strong"

    SOCIAL_AUTH_LOGIN_URL = "/login"
    SOCIAL_AUTH_LOGIN_REDIRECT_URL = "/"
    SOCIAL_AUTH_DISCONNECT_REDIRECT_URL = "/logout"
    SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
    SOCIAL_AUTH_USER_MODEL = "member_card.models.user.User"
    SOCIAL_AUTH_STORAGE = "social_flask_sqlalchemy.models.FlaskStorage"
    SOCIAL_AUTH_AUTHENTICATION_BACKENDS = ("social_core.backends.google.GoogleOAuth2",)

    DB_CONNECTION_NAME = "lv-digital-membership:us-central1:lv-digital-membership"
    DB_USERNAME = "website"
    DB_DATABASE_NAME = "lv-digital-membership"

    SQLALCHEMY_DATABASE_URI = "postgresql://member-card-user:member-card-password@127.0.0.1:5433/digital-membership"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SOCIAL_AUTH_TRAILING_SLASH = True

    SOCIAL_AUTH_PIPELINE = (
        "social_core.pipeline.social_auth.social_details",
        "social_core.pipeline.social_auth.social_uid",
        "social_core.pipeline.social_auth.auth_allowed",
        "social_core.pipeline.social_auth.social_user",
        "member_card.utils.get_username",
        "social_core.pipeline.mail.mail_validation",
        "social_core.pipeline.social_auth.associate_by_email",
        "social_core.pipeline.user.create_user",
        "social_core.pipeline.social_auth.associate_user",
        "social_core.pipeline.debug.debug",
        "social_core.pipeline.social_auth.load_extra_data",
        "social_core.pipeline.user.user_details",
        "social_core.pipeline.debug.debug",
    )

    SOCIAL_AUTH_DISCONNECT_PIPELINE = (
        # Verifies that the social association can be disconnected from the current
        # user (ensure that the user login mechanism is not compromised by this
        # disconnection).
        # "social_core.pipeline.disconnect.allowed_to_disconnect",  # we're "cool" if someone "locks"(?) themselves out?
        # Collects the social associations to disconnect.
        "social_core.pipeline.disconnect.get_entries",
        # Revoke any access_token when possible.
        "social_core.pipeline.disconnect.revoke_tokens",
        # Removes the social associations.
        "social_core.pipeline.disconnect.disconnect",
    )


class DockerComposeSettings(Settings):
    pass
    # SQLALCHEMY_DATABASE_URI = "postgresql://member-card-user:member-card-password@db:5432/digital-membership"
    SQLALCHEMY_DATABASE_URI = "postgresql://member-card-user:member-card-password@127.0.0.1:5432/digital-membership"


class ProductionSettings(Settings):
    DEBUG = False
    SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
    SQLALCHEMY_DATABASE_URI = "postgresql+pg8000://"

    def __init__(self) -> None:

        super().__init__()
        self.SOCIAL_AUTH_PIPELINE = tuple(
            [p for p in self.SOCIAL_AUTH_PIPELINE if not p.endswith("debug")]
        )
        # from: https://realpython.com/flask-google-login/
        if secrets_json := os.getenv("DIGITAL_MEMBERSHIP_SECRETS_JSON"):
            self._secrets = json.loads(secrets_json)

        self.export_secrets_as_settings()
        self.use_gcp_sql_connector()
        logger.debug(f"{self.SQLALCHEMY_ENGINE_OPTIONS=}")


class RemoteSqlProductionSettings(ProductionSettings):
    SQLALCHEMY_ECHO = True

    def __init__(self) -> None:
        if secret_name := os.getenv("DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"):
            logger.info(f"Loading secrets from {secret_name=}")
            from member_card.secrets import retrieve_app_secrets

            if not self._secrets:
                self._secrets = retrieve_app_secrets(secret_name)

        # Setting DB_USERNAME explicitly here so local users can use their own gcloud auth creds:
        if local_db_username := os.getenv("DB_USERNAME"):
            self._secrets["db_username"] = local_db_username

        super().__init__()


def get_settings_obj_for_env(env=None, default_settings_class=Settings):
    if env is None:
        env = os.getenv("FLASK_ENV", "unknown").lower().strip()

    settings_objs_by_env = {
        "compose": DockerComposeSettings,
        "production": ProductionSettings,
        "remote-sql": RemoteSqlProductionSettings,
    }

    return settings_objs_by_env.get(env, default_settings_class)
