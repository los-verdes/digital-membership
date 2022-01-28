#!/usr/bin/env python
import os
from member_card.secrets import retrieve_app_secrets
from logzero import logger
from member_card.db import squarespace_orders_etl
from member_card.squarespace import Squarespace


MEMBERSHIP_SKU = os.getenv("DIGITAL_MEMBERSHIP_SKU")


def sync_subscriptions(event, context):

    print(
        """This Function was triggered by messageId {} published at {} to {}
    """.format(
            context.event_id, context.timestamp, context.resource["name"]
        )
    )

    print("Hello {}!".format(event))

    secret_name = os.getenv("DIGITAL_MEMBERSHIP_GCP_SECRET_NAME")
    if secret_name is None:
        raise Exception(
            f"Unable to retrieve secrets for syncing, DIGITAL_MEMBERSHIP_GCP_SECRET_NAME env var unset!: {secret_name=}"
        )

    logger.info(f"Loading secrets from {secret_name=}")

    load_all = event.get("load_all", False)

    squarespace = Squarespace(
        api_key=retrieve_app_secrets(secret_name)["SQUARESPACE_API_KEY"]
    )

    from member_card import create_app

    create_app()
    from member_card.db import db

    etl_results = squarespace_orders_etl(
        squarespace_client=squarespace,
        db_session=db.session,
        membership_sku=MEMBERSHIP_SKU,
        load_all=load_all,
    )
    logger.debug(f"{etl_results=}")
