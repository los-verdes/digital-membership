import os

from member_card.settings import Settings


class ProductionSettings(Settings):
    GCP_SECRET_NAME = os.getenv("DIGITAL_MEMBERSHIP_GCP_SECRET_NAME")
    # from: https://realpython.com/flask-google-login/
    if GCP_SECRET_NAME:
        from member_card.secrets import retrieve_app_secrets

        secrets = retrieve_app_secrets(GCP_SECRET_NAME)
        SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = secrets["oauth_client_id"]
        SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = secrets["oauth_client_secret"]
        SECRET_KEY = secrets["flask_secret_key"]
    else:
        raise Exception(
            "Unable to load production settings, no secret version name found under  "
        )

    SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
