import os
from os.path import dirname, abspath, join
from logzero import logger


class Settings(object):
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

    SOCIAL_AUTH_LOGIN_URL = "/"
    SOCIAL_AUTH_LOGIN_REDIRECT_URL = "/"
    SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
    SOCIAL_AUTH_USER_MODEL = "member_card.models.user.User"
    SOCIAL_AUTH_STORAGE = "social_flask_sqlalchemy.models.FlaskStorage"
    SOCIAL_AUTH_AUTHENTICATION_BACKENDS = ("social_core.backends.google.GoogleOAuth2",)

    POSTGRES_CONNECTION_NAME = "lv-digital-membership:us-central1:lv-digital-membership"
    POSTGRES_USER = "website"
    POSTGRES_PASS = None
    POSTGRES_DB = "lv-digital-membership"

    SQLALCHEMY_DATABASE_URI = "postgresql://member-card-user:member-card-password@127.0.0.1:5432/digital-membership"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SOCIAL_AUTH_TRAILING_SLASH = True

    SOCIAL_AUTH_PIPELINE = (
        "social_core.pipeline.social_auth.social_details",
        "social_core.pipeline.social_auth.social_uid",
        "social_core.pipeline.social_auth.auth_allowed",
        "social_core.pipeline.social_auth.social_user",
        "social_core.pipeline.user.get_username",
        "social_core.pipeline.mail.mail_validation",
        "social_core.pipeline.social_auth.associate_by_email",
        "social_core.pipeline.user.create_user",
        "social_core.pipeline.social_auth.associate_user",
        "social_core.pipeline.debug.debug",
        "social_core.pipeline.social_auth.load_extra_data",
        "social_core.pipeline.user.user_details",
        "social_core.pipeline.debug.debug",
    )


class ProductionSettings(Settings):
    secrets = None

    def __init__(self) -> None:
        super().__init__()
        # from: https://realpython.com/flask-google-login/
        if secret_name := os.getenv("DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"):
            from member_card.secrets import retrieve_app_secrets

            if ProductionSettings.secrets is None:
                ProductionSettings.secrets = retrieve_app_secrets(secret_name)
            self.secrets = ProductionSettings.secrets
            self.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = self.secrets["oauth_client_id"]
            self.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = self.secrets["oauth_client_secret"]
            self.SECRET_KEY = self.secrets["flask_secret_key"]
            self.POSTGRES_USER = self.secrets["sql_username"]
            logger.warning("setting prod sql_password...")
            # breakpoint()
            self.POSTGRES_PASS = self.secrets["sql_password"]

            db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
            # db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/tmp/cloudsql")
            logger.debug(f"{db_socket_dir=}")

            self.APPLE_DEVELOPER_CERTIFICATE = self.secrets["apple_pass_certificate"]
            self.APPLE_DEVELOPER_PRIVATE_KEY = self.secrets["apple_pass_private_key"]
            self.APPLE_DEVELOPER_PRIVATE_KEY_PASSWORD = self.secrets[
                "apple_pass_private_key_password"
            ]
            # self.SQLALCHEMY_DATABASE_URI = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASS}@127.0.0.1:5432/lv-digital-membership"
            # self.SQLALCHEMY_DATABASE_URI =
            # f"postgresql+pg8000://{self.POSTGRES_USER}:{self.POSTGRES_PASS}@lv-digital-membership
            # ?
            # unix_sock={db_socket_dir}/lv-digital-membership:us-central1:lv-digital-membership/.s.PGSQL.5432"
            from sqlalchemy import engine

            self.SQLALCHEMY_DATABASE_URI = getattr(engine, "url").URL.create(
                drivername="postgresql+pg8000",
                username=self.POSTGRES_USER,  # e.g. "my-database-user"
                password=self.POSTGRES_PASS,  # e.g. "my-database-password"
                database=self.secrets["sql_database_name"],  # e.g. "my-database-name"
                query={
                    "unix_sock": "{}/{}/.s.PGSQL.5432".format(
                        db_socket_dir,  # e.g. "/cloudsql"
                        self.secrets[
                            "sql_connection_name"
                        ],  # i.e "<PROJECT-NAME>:<INSTANCE-REGION>:<INSTANCE-NAME>"
                    )
                },
            )

        else:
            raise Exception(
                "Unable to load production settings, no secret version name found under  "
            )

    SOCIAL_AUTH_REDIRECT_IS_HTTPS = True


class RemoteSqlSettings(ProductionSettings):
    def __init__(self) -> None:
        super().__init__()
        # from: https://realpython.com/flask-google-login/
        if secret_name := os.getenv("DIGITAL_MEMBERSHIP_GCP_SECRET_NAME"):
            from member_card.secrets import retrieve_app_secrets

            if ProductionSettings.secrets is None:
                ProductionSettings.secrets = retrieve_app_secrets(secret_name)
            self.secrets = ProductionSettings.secrets
            self.POSTGRES_USER = self.secrets["sql_username"]
            logger.warning("setting prod sql_password...")
            # breakpoint()
            self.POSTGRES_PASS = self.secrets["sql_password"]

            db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
            # db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/tmp/cloudsql")
            logger.debug(f"{db_socket_dir=}")
            self.SQLALCHEMY_DATABASE_URI = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASS}@127.0.0.1:5432/lv-digital-membership"


def get_settings_obj_for_env(env=None, default_settings_class=Settings):
    if env is None:
        env = os.getenv("FLASK_ENV", "unknown").lower().strip()

    class DockerComposeSettings(Settings):
        pass
        # SQLALCHEMY_DATABASE_URI = "postgresql://member-card-user:member-card-password@db:5432/digital-membership"
        SQLALCHEMY_DATABASE_URI = "postgresql://member-card-user:member-card-password@127.0.0.1:5432/digital-membership"

    if env == "production":

        return ProductionSettings()

    settings_objs_by_env = {
        # "default": Settings,
        "compose": DockerComposeSettings,
        # "production": ProductionSettings,
    }

    return settings_objs_by_env.get(env, default_settings_class)
