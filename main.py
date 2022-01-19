#!/usr/bin/env python
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import logzero
from logzero import logger

from member_card.squarespace import Squarespace


# def get_profile_by_email(squarespace, email):
#     resp = squarespace.get_profile_by_email(
#         email=email,
#     )
#     logger.debug(f"get_profile_by_email(email={email}) => {resp}")
#     print(json.dumps(resp))


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
        "-e",
        "--email",
        default="jeff.hogan1@gmail.com",
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
    email = args.email
    membership_sku = args.membership_sku

    squarespace = Squarespace(api_key=os.environ["SQUARESPACE_API_KEY"])

    # get_profile_by_email(
    #     squarespace=squarespace,
    #     email=args.email,
    # )

    modified_before_dt = datetime.now(tz=ZoneInfo("UTC"))
    modified_after_dt = modified_before_dt - timedelta(days=30)
    modified_after = modified_after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    modified_before = modified_before_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # subscriptions = squarespace.load_membership_orders_datetime_window(
    #     membership_sku=membership_sku,
    #     modified_after=modified_after,
    #     modified_before=modified_before,
    #     fulfillment_status=args.fulfillment_status,
    # )

    subscriptions = squarespace.load_all_membership_orders(
        membership_sku=membership_sku,
        order_params=dict(fulfillment_status=args.fulfillment_status),
    )

    active_subscriptions = [s for s in subscriptions if s.is_active]
    inactive_subscriptions = [s for s in subscriptions if not s.is_active]
    logger.info(
        f"Stats: {len(subscriptions)=} / {len(active_subscriptions)=} / {len(inactive_subscriptions)=}"
    )
    subscriptions_by_email = defaultdict(list)
    for subscription in subscriptions:
        subscriptions_by_email[subscription.customer_email].append(subscription)

    if matching_subscriptions := subscriptions_by_email.get(email):
        logger.info(f"Subscription found for {email}:\n{matching_subscriptions}")
        if any(s.is_active for s in matching_subscriptions):
            print("<print membership card here>")
            exit(0)

    logger.warning(
        "<no active subscriptions / matching subscriptions ever / access denied>"
    )
    exit(1)
