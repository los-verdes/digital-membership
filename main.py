#!/usr/bin/env python
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

import logzero
from dateutil.parser import parse
from logzero import logger

from member_card.squarespace import Squarespace


class AnnualSubscription(object):
    one_year_ago = datetime.now(tz=ZoneInfo("UTC")) - timedelta(days=366)

    def __init__(self, order):
        self._order = order
        self.created_on = parse(self._order["createdOn"])

    def __getattr__(self, key):
        if value := self._order.get(key):
            return value
        # convert key from snake to camel case
        components = key.split("_")
        # via: https://stackoverflow.com/a/19053800
        # We capitalize the first letter of each component except the first one
        # with the 'title' method and join them together.
        camelKey = components[0] + "".join(x.title() for x in components[1:])
        if value := self._order.get(camelKey):
            return value

        raise AttributeError(f"no {key=} in <AnnualSubscription _order... >")

    def __repr__(self):
        return " ".join(
            [
                "<AnnualSubscription",
                self.customer_email,
                self.created_on.isoformat(),
                f"fulfillment_status={self.fulfillment_status}",
                f"(active={self.is_active})",
                " ... >",
            ]
        )

    @property
    def is_canceled(self):
        return self.fulfillment_status == "CANCELED"

    @property
    def is_active(self):
        if self.is_canceled:
            return False
        if self.created_on <= self.one_year_ago:
            return False

        return True


# def get_profile_by_email(squarespace, email):
#     resp = squarespace.get_profile_by_email(
#         email=email,
#     )
#     logger.debug(f"get_profile_by_email(email={email}) => {resp}")
#     print(json.dumps(resp))


def load_membership_orders_datetime_window(
    squarespace, modified_before=None, modified_after=None, fulfillment_status=None
) -> List[AnnualSubscription]:
    order_params = dict(
        modifiedAfter=modified_after,
        modifiedBefore=modified_before,
        fulfillmentStatus=fulfillment_status,
    )

    return load_all_membership_orders(
        squarespace=squarespace, order_params=order_params
    )


def load_all_membership_orders(squarespace, order_params) -> List[AnnualSubscription]:
    # remove "None"s
    order_params = {k: v for k, v in order_params.items() if v is not None}

    all_orders = []
    subscriptions = []

    logger.debug(f"Grabbing all orders with {order_params=}")

    for order in squarespace.all_orders(**order_params):
        all_orders.append(order)

        order_product_names = [i["productName"] for i in order["lineItems"]]
        if any(i["sku"] == membership_sku for i in order["lineItems"]):
            logger.debug(
                f"{order['id']=} (#{order['orderNumber']}) includes {membership_sku=} in {order_product_names=}"
            )
            subscriptions.append(AnnualSubscription(order))
            continue
        logger.debug(
            f"#{order['orderNumber']} has no {membership_sku=} in {order_product_names=}"
        )

    logger.debug(f"{len(all_orders)=} loaded with {len(subscriptions)=} and whatnot")
    return subscriptions


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

    # subscriptions = load_membership_orders_datetime_window(
    #     squarespace=squarespace,
    #     modified_after=modified_after,
    #     modified_before=modified_before,
    #     fulfillment_status=args.fulfillment_status,
    # )

    subscriptions = load_all_membership_orders(
        squarespace=squarespace,
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
