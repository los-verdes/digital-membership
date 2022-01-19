#!/usr/bin/env python
import logging
import os

import logzero
from logzero import logger

from member_card.db import get_firestore_client
from member_card.squarespace import Squarespace, AnnualMembership

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-q",
        "--quiet",
        help="modify output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "-m",
        "--membership-sku",
        default="SQ3671268",
    )
    parser.add_argument(
        "-f",
        "--fulfillment-status",
        choices=["PENDING", "FULFILLED", "CANCELED", None],
        default=None,
    )
    args = parser.parse_args()
    if args.quiet:
        logzero.loglevel(logging.INFO)

    membership_sku = args.membership_sku

    squarespace = Squarespace(api_key=os.environ["SQUARESPACE_API_KEY"])

    subscriptions = squarespace.load_all_membership_orders(
        membership_sku=membership_sku,
        order_params=dict(fulfillment_status=args.fulfillment_status),
    )

    # from datetime import datetime, timedelta
    # from zoneinfo import ZoneInfo

    # modified_before_dt = datetime.now(tz=ZoneInfo("UTC"))
    # modified_after_dt = modified_before_dt - timedelta(days=3)
    # modified_after = modified_after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    # modified_before = modified_before_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # subscriptions = squarespace.load_membership_orders_datetime_window(
    #     membership_sku=membership_sku,
    #     modified_after=modified_after,
    #     modified_before=modified_before,
    #     fulfillment_status=args.fulfillment_status,
    # )

    active_subscriptions = [s for s in subscriptions if s.is_active]
    inactive_subscriptions = [s for s in subscriptions if not s.is_active]
    logger.info(
        f"Stats: {len(subscriptions)=} / {len(active_subscriptions)=} / {len(inactive_subscriptions)=}"
    )
    # breakpoint()
    db = get_firestore_client()
    memberships_ref = db.collection("memberships")
    for subscription in subscriptions:
        # if subscription.customer_email != "jeff.hogan1@gmail.com":
        #     continue
        membership_ref = memberships_ref.document(subscription.id)
        # breakpoint()
        if membership_ref.get().exists:
            logger.debug(f"Updating firestore document for: {subscription.id=}")
        else:
            logger.debug(f"Creating firestore document for: {subscription.id=}")
            membership_ref.set(subscription.to_dict())
        # breakpoint()
