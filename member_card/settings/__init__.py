import os
from os.path import dirname, abspath, join


class Settings(object):
    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get("GOOGLE_CLIENT_ID", None)
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = os.getenv("GOOGLE_OAUTH2_SCOPE", [])
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

    # from: https://github.com/python-social-auth/social-examples
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24)
    SESSION_COOKIE_NAME = "psa_session"
    DEBUG = True
    DATABASE_URI = "%s/db.sqlite3" % dirname(abspath(join(__file__, "..")))
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    SESSION_PROTECTION = "strong"

    SOCIAL_AUTH_LOGIN_URL = "/"
    SOCIAL_AUTH_LOGIN_REDIRECT_URL = "/"
    SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
    SOCIAL_AUTH_USER_MODEL = "member_card.models.user.User"
    SOCIAL_AUTH_STORAGE = "social_flask_peewee.models.FlaskStorage"
    SOCIAL_AUTH_AUTHENTICATION_BACKENDS = ("social_core.backends.google.GoogleOAuth2",)

    SOCIAL_AUTH_TRAILING_SLASH = True

    SOCIAL_AUTH_PIPELINE = (
        "social_core.pipeline.social_auth.social_details",
        "social_core.pipeline.social_auth.social_uid",
        "social_core.pipeline.social_auth.auth_allowed",
        "social_core.pipeline.social_auth.social_user",
        "social_core.pipeline.user.get_username",
        "social_core.pipeline.mail.mail_validation",
        "social_core.pipeline.user.create_user",
        "social_core.pipeline.social_auth.associate_user",
        "social_core.pipeline.debug.debug",
        "social_core.pipeline.social_auth.load_extra_data",
        "social_core.pipeline.user.user_details",
        "social_core.pipeline.debug.debug",
    )
