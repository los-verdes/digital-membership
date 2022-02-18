import json
import logging
import os
from functools import partial
from typing import TYPE_CHECKING, Tuple

from google.cloud.sql.connector import connector

if TYPE_CHECKING:
    from pg8000 import dbapi

logger = logging.getLogger("member_card")


class Settings(object):
    _secrets: dict = dict()

    APPLE_DEVELOPER_ORG_NAME: str = "Jeffrey Hogan"  # TODO: if LV is a legit 501c this can maybe become a less personal org...
    APPLE_DEVELOPER_PASS_TYPE_ID: str = "pass.es.losverd.card"
    APPLE_DEVELOPER_TEAM_ID: str = "KJHZP635V9"

    APPLE_DEVELOPER_CERTIFICATE: str = os.environ.get("APPLE_DEVELOPER_CERTIFICATE", "")
    APPLE_KEY_FILEPATH: str = os.environ.get(
        "APPLE_KEY_FILEPATH", "/apple-secrets/private.key"
    )
    APPLE_DEVELOPER_PRIVATE_KEY: str = os.environ.get("APPLE_DEVELOPER_PRIVATE_KEY", "")

    APPLE_PASS_PRIVATE_KEY_PASSWORD: str = os.environ.get(
        "APPLE_PASS_PRIVATE_KEY_PASSWORD", ""
    )

    GOOGLE_PAY_ISSUER_NAME: str = os.environ.get("GOOGLE_PAY_ISSUER_NAME", "Los Verdes")
    GOOGLE_PAY_ISSUER_ID: str = os.environ.get(
        "GOOGLE_PAY_ISSUER_ID", "3388000000022031577"
    )
    GOOGLE_PAY_PASS_CLASS_ID: str = os.environ.get(
        "GOOGLE_PAY_PASS_CLASS_ID", f"{GOOGLE_PAY_ISSUER_ID}.membership-card-2021-v0"
    )
    GOOGLE_PAY_PROGRAM_NAME: str = os.environ.get(
        "GOOGLE_PAY_PROGRAM_NAME", "Membership Card"
    )
    GOOGLE_PAY_SERVICE_ACCOUNT_EMAIL_ADDRESS: str = os.getenv(
        "GOOGLE_PAY_SERVICE_ACCOUNT_EMAIL_ADDRESS", ""
    )
    GOOGLE_PAY_SERVICE_ACCOUNT_FILE: str = os.getenv(
        "GOOGLE_PAY_SERVICE_ACCOUNT_FILE", "/secrets/service-account-key.json"
    )
    GOOGLE_PAY_ORIGINS = [
        "https://card.losverd.es",
        "https://localcard.losverd.es:5000",
        # "https://pay.google.com",
    ]

    # Constants that are application agnostic. Used for JWT
    GOOGLE_PAY_AUDIENCE = "google"
    GOOGLE_PAY_JWT_TYPE = "savetoandroidpay"
    GOOGLE_PAY_SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

    GOOGLE_DISCOVERY_URL: str = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )
    SERVICE_ACCOUNT_KEY: str = os.getenv("SERVICE_ACCOUNT_KEY", "")
    GCS_BUCKET_ID: str = os.getenv("GCS_BUCKET_ID", "")
    GCLOUD_PROJECT: str = os.getenv("GCLOUD_PROJECT", "")
    GCP_REPO_NAME: str = os.getenv(
        "GCP_REPO_NAME", "github_los-verdes_digital-membership"
    )
    GCLOUD_PUBSUB_TOPIC_ID: str = os.getenv(
        "GCLOUD_PUBSUB_TOPIC_ID", "digital-membership"
    )

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    CLOUD_RUN_SERVICE: str = os.getenv("K_SERVICE", "N/A")
    CLOUD_RUN_REVISION: str = os.getenv("K_REVISION", "N/A")
    CLOUD_RUN_CONFIGURATION: str = os.getenv("K_SERVICE", "N/A")
    RUNNING_ON_CLOUD_RUN: bool = CLOUD_RUN_SERVICE != "N/A"
    TRACING_ENABLED: bool = RUNNING_ON_CLOUD_RUN

    # https://stackoverflow.com/a/53214929
    CDN_DOMAIN = os.getenv("GCS_BUCKET_ID", "")
    STATIC_ASSET_BASE_URL = f"https://{CDN_DOMAIN}/static"
    CDN_TIMESTAMP = False
    CDN_DEBUG = True
    CDN_HTTPS = True
    FLASK_ASSETS_USE_CDN = True

    DB_CONNECTION_NAME: str = os.environ["DIGITAL_MEMBERSHIP_DB_CONNECTION_NAME"]
    DB_USERNAME: str = os.environ["DIGITAL_MEMBERSHIP_DB_USERNAME"]
    DB_DATABASE_NAME: str = os.environ["DIGITAL_MEMBERSHIP_DB_DATABASE_NAME"]
    DB_PASSWORD: str = os.getenv("DIGITAL_MEMBERSHIP_DB_ACCESS_TOKEN")

    BASE_URL: str = (
        f'https://{os.getenv("DIGITAL_MEMBERSHIP_BASE_URL", "card.losverd.es")}'
    )

    DEBUG: bool = True
    # from: https://github.com/python-social-auth/social-examples
    DEBUG_TB_INTERCEPT_REDIRECTS: bool = False

    EMAIL_FROM_ADDRESS: str = os.getenv("EMAIL_FROM_ADDRESS", "verde-bot@losverd.es")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "Los Verdes (verde-bot)")
    EMAIL_SUBJECT_TEXT: str = os.getenv(
        "EMAIL_SUBJECT_TEXT", "Los Verdes Membership Card Details"
    )

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    RECAPTCHA_SITE_KEY: str = os.getenv(
        "RECAPTCHA_SITE_KEY", "6LdAblIeAAAAADLSJxAgNOhI2vSnZTG8rurt7Pnt"
    )
    RECAPTCHA_SECRET_KEY: str = os.getenv("RECAPTCHA_SECRET_KEY", "")
    RECAPTCHA_SIZE = "compact"

    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_GROUP_ID: str = os.getenv("SENDGRID_GROUP_ID", "29631")
    SENDGRID_TEMPLATE_ID: str = os.getenv(
        "SENDGRID_TEMPLATE_ID", "d-626729a6eed9402fa4ce849d8227afc4"
    )
    # SERVER_NAME: str = os.getenv("SERVER_NAME", "card.losverd.es")

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
    SQUARESPACE_CLIENT_ID: str = os.getenv("SQUARESPACE_CLIENT_ID", "")
    SQUARESPACE_CLIENT_SECRET: str = os.getenv("SQUARESPACE_CLIENT_SECRET", "")
    SQUARESPACE_OAUTH_REDIRECT_URI: str = f"{BASE_URL}/squarespace/oauth/connect"
    SQUARESPACE_ALLOWED_WEBSITE_IDS = [
        "620c2c763b1f5c0f1b713afe",  # JHOG's test site
        "5ec4a139657fe864073c26e6",  # losverdesatx.org
    ]
    SQUARESPACE_ORDER_WEBHOOK_ENDPOINT: str = f"{BASE_URL}/squarespace/order-webhook"
    SQUARESPACE_MEMBERSHIP_SKUS = os.getenv(
        "SQUARESPACE_MEMBERSHIP_SKUS", "SQ3671268,SQ6438806"
    ).split(",")

    SESSION_PROTECTION: str = "strong"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "not-very-secret-at-all")
    SESSION_COOKIE_NAME: str = "psa_session"

    SQLALCHEMY_DATABASE_URI: str = "postgresql://member-card-user:member-card-password@127.0.0.1:5433/digital-membership"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    def export_dict_as_settings(self, dict_to_export: dict[str, str]) -> None:
        for key, value in dict_to_export.items():
            settings_key = key.upper()
            logger.debug(f"Exporting {key} as settings key: {settings_key}")
            setattr(self, settings_key, value)

    def export_secrets_as_settings(self) -> None:
        logger.debug(f"Exporting {list(self._secrets.keys())} as setting attributes...")
        self.export_dict_as_settings(self._secrets)

    def use_gcp_sql_connector(self) -> None:
        db_connection_kwargs = dict(
            instance_connection_string=self.DB_CONNECTION_NAME,
            db_user=self.DB_USERNAME,
            db_name=self.DB_DATABASE_NAME,
            db_pass=self.DB_PASSWORD,
        )

        logger.debug({k: f"{v[:3]}...{v[-3:]}" for k, v in db_connection_kwargs.items() if v is not None})

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
        self.SQLALCHEMY_ENGINE_OPTIONS = dict(
            creator=engine_creator,
        )

    def __init__(self) -> None:
        logger.debug(f"Initializing settings class: {type(self)}...")
        logger.info("env var keys", extra=dict(env_var_keys=list(os.environ.keys())))
        if secrets_json := os.getenv("DIGITAL_MEMBERSHIP_SECRETS_JSON"):
            self._secrets = json.loads(secrets_json)
        elif secret_name := os.getenv("DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"):
            logger.info(f"Loading secrets from {secret_name=}")
            from member_card.secrets import retrieve_app_secrets

            if not self._secrets:
                self._secrets = retrieve_app_secrets(secret_name)

        self.export_secrets_as_settings()
        logger.debug(f"Initialized settings class!: {type(self)}...")

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
    SQLALCHEMY_ECHO: bool = False
    CDN_DEBUG = False

    def __init__(self) -> None:

        super().__init__()
        self.SOCIAL_AUTH_PIPELINE = tuple(
            [p for p in self.SOCIAL_AUTH_PIPELINE if not p.endswith("debug")]
        )
        # from: https://realpython.com/flask-google-login/
        self.use_gcp_sql_connector()
        logger.debug(f"{self.SQLALCHEMY_ENGINE_OPTIONS=}")


class DevelopementSettings(Settings):
    SQLALCHEMY_ECHO: bool = False


class RemoteSqlProductionSettings(ProductionSettings):
    def __init__(self) -> None:

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
