import json
import os
from functools import partial
from typing import TYPE_CHECKING, Tuple

from google.cloud.sql.connector import connector

# from logzero import logger
import logging

if TYPE_CHECKING:
    from pg8000 import dbapi


class Settings(object):
    _secrets: dict = dict()

    APPLE_DEVELOPER_ORG_NAME: str = "Jeffrey Hogan"  # TODO: if LV is a legit 501c this can maybe become a less personal org...
    APPLE_DEVELOPER_PASS_TYPE_ID: str = "pass.es.losverd.card"
    APPLE_DEVELOPER_TEAM_ID: str = "KJHZP635V9"

    APPLE_DEVELOPER_CERTIFICATE: str = os.environ.get("APPLE_DEVELOPER_CERTIFICATE", "")
    APPLE_DEVELOPER_PRIVATE_KEY: str = os.environ.get("APPLE_DEVELOPER_PRIVATE_KEY", "")
    APPLE_PASS_PRIVATE_KEY_PASSWORD: str = os.environ.get(
        "APPLE_PASS_PRIVATE_KEY_PASSWORD", ""
    )

    DB_CONNECTION_NAME: str = os.environ["DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME"]
    DB_USERNAME: str = os.environ["DIGITAL_MEMBERSHIP_DB_USERNAME"]
    DB_DATABASE_NAME: str = os.environ["DIGITAL_MEMBERSHIP_DB_DATABASE_NAME"]

    DEBUG: bool = True
    # from: https://github.com/python-social-auth/social-examples
    DEBUG_TB_INTERCEPT_REDIRECTS: bool = False

    GOOGLE_DISCOVERY_URL: str = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    SOCIAL_AUTH_DISCONNECT_REDIRECT_URL: str = "/logout"
    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    SOCIAL_AUTH_LOGIN_REDIRECT_URL: str = "/"
    SOCIAL_AUTH_LOGIN_URL: str = "/login"
    SOCIAL_AUTH_REDIRECT_IS_HTTPS: bool = True
    SOCIAL_AUTH_STORAGE: str = "social_flask_sqlalchemy.models.FlaskStorage"
    SOCIAL_AUTH_TRAILING_SLASH: bool = True
    SOCIAL_AUTH_USER_MODEL: str = "member_card.models.user.User"

    SOCIAL_AUTH_PIPELINE: Tuple[str, ...] = (
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

    SOCIAL_AUTH_AUTHENTICATION_BACKENDS: Tuple[str, ...] = (
        "social_core.backends.google.GoogleOAuth2",
    )

    SOCIAL_AUTH_DISCONNECT_PIPELINE: Tuple[str, ...] = (
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

    SQUARESPACE_API_KEY: str = os.getenv("SQUARESPACE_API_KEY", "")

    SESSION_PROTECTION: str = "strong"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "not-very-secret-at-all")
    SESSION_COOKIE_NAME: str = "psa_session"

    SQLALCHEMY_DATABASE_URI: str = "postgresql://member-card-user:member-card-password@127.0.0.1:5433/digital-membership"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    def export_dict_as_settings(self, dict_to_export: dict[str, str]) -> None:
        for key, value in dict_to_export.items():
            settings_key = key.upper()
            logging.debug(f"Exporting {key} as settings key: {settings_key}")
            setattr(self, settings_key, value)

    def export_secrets_as_settings(self) -> None:
        logging.debug(
            f"Exporting {list(self._secrets.keys())} as setting attributes..."
        )
        self.export_dict_as_settings(self._secrets)

    def use_gcp_sql_connector(self) -> None:
        db_connection_kwargs = dict(
            instance_connection_string=self.DB_CONNECTION_NAME,
            db_user=self.DB_USERNAME,
            db_name=self.DB_DATABASE_NAME,
        )

        logging.debug(f"{db_connection_kwargs=}")

        def get_db_connector(
            instance_connection_string: str, db_user: str, db_name: str
        ) -> "dbapi.Connection":
            conn: "dbapi.Connection" = connector.connect(
                instance_connection_string,
                "pg8000",
                user=db_user,
                db=db_name,
                password=os.getenv('DIGITAL_MEMBERSHIP_DB_ACCESS_TOKEN'),  # TODO: surface this env var higher up in the class??
                enable_iam_auth=True,
            )
            return conn

        engine_creator = partial(get_db_connector, **db_connection_kwargs)
        self.SQLALCHEMY_ENGINE_OPTIONS = dict(
            creator=engine_creator,
        )

    def __init__(self) -> None:
        logging.debug(f"Initializing settings class: {type(self)}...")
        logging.info("env var keys", extra=dict(env_var_keys=list(os.environ.keys())))

    def assert_required_settings_present(self) -> None:
        pass


class DockerComposeSettings(Settings):
    pass
    # SQLALCHEMY_DATABASE_URI: str = "postgresql://member-card-user:member-card-password@db:5432/digital-membership"
    SQLALCHEMY_DATABASE_URI: str = "postgresql://member-card-user:member-card-password@127.0.0.1:5432/digital-membership"


class ProductionSettings(Settings):
    DEBUG: bool = False
    SOCIAL_AUTH_REDIRECT_IS_HTTPS: bool = True
    SQLALCHEMY_DATABASE_URI: str = "postgresql+pg8000://"

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
        logging.debug(f"{self.SQLALCHEMY_ENGINE_OPTIONS=}")


class RemoteSqlProductionSettings(ProductionSettings):
    SQLALCHEMY_ECHO: bool = True

    def __init__(self) -> None:
        if secret_name := os.getenv("DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"):
            logging.info(f"Loading secrets from {secret_name=}")
            from member_card.secrets import retrieve_app_secrets

            if not self._secrets:
                self._secrets = retrieve_app_secrets(secret_name)

        super().__init__()


def get_settings_obj_for_env(env: str = None, default_settings_class=Settings):
    if env is None:
        env = os.getenv("FLASK_ENV", "unknown").lower().strip()

    settings_objs_by_env = {
        "compose": DockerComposeSettings,
        "production": ProductionSettings,
        "remote-sql": RemoteSqlProductionSettings,
    }

    return settings_objs_by_env.get(env, default_settings_class)
