#!/usr/bin/env python
import logging
import os

import logzero
from dateutil.parser import parse
from logzero import logger

from member_card.models import AnnualMembership, TableMetadata
from member_card.squarespace import Squarespace
from member_card import db_session

# from member_card import db
# from member_card.utils import get_db_session

# from member_card.db import get_firestore_client


def get_or_create(session, model, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    # for k, v in kwargs.items():
    #     logger.warning(f"{k} : {type(v)}")
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        # session.commit()
        return instance


def load_membership_orders_datetime_window(
    squarespace,
    membership_sku,
    modified_before=None,
    modified_after=None,
    fulfillment_status=None,
):
    # ) -> List[AnnualMembership]:
    order_params = dict(
        modifiedAfter=modified_after,
        modifiedBefore=modified_before,
        fulfillmentStatus=fulfillment_status,
    )

    return load_all_membership_orders(
        squarespace, membership_sku, order_params=order_params
    )


def load_all_membership_orders(squarespace, membership_sku, order_params):
    # ) -> List[AnnualMembership]:
    # remove "None"s
    order_params = {k: v for k, v in order_params.items() if v is not None}

    all_orders = []
    membership_orders = []

    logger.debug(f"Grabbing all orders with {order_params=}")

    for order in squarespace.all_orders(**order_params):
        all_orders.append(order)

        order_product_names = [i["productName"] for i in order["lineItems"]]
        if any(i["sku"] == membership_sku for i in order["lineItems"]):
            logger.debug(
                f"{order['id']=} (#{order['orderNumber']}) includes {membership_sku=} in {order_product_names=}"
            )
            membership_orders.append(order)
            continue
        logger.debug(
            f"#{order['orderNumber']} has no {membership_sku=} in {order_product_names=}"
        )

    logger.debug(
        f"{len(all_orders)=} loaded with {len(membership_orders)=} and whatnot"
    )
    return membership_orders


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
        "-l",
        "--load-all",
        help="load all orders",
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

    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    start_time = datetime.now(tz=ZoneInfo("UTC"))
    # db_session = get_db_session()
    instance = (
        db_session.query(TableMetadata)
        .filter_by(
            table_name=AnnualMembership.__tablename__,
            attribute_name="last_run_start_time",
        )
        .first()
    )
    # modified_before_dt = datetime.now(tz=ZoneInfo("UTC"))

    if instance and not args.load_all:
        logger.debug(f"{instance=}")
        modified_after_dt = datetime.fromtimestamp(
            float(instance.attribute_value)
        ) - timedelta(days=1)
        # modified_after_dt = start_time - timedelta(days=3)
        modified_after = modified_after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        modified_before = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        subscription_orders = load_membership_orders_datetime_window(
            squarespace=squarespace,
            membership_sku=membership_sku,
            modified_after=modified_after,
            modified_before=modified_before,
            fulfillment_status=args.fulfillment_status,
        )

    else:
        subscription_orders = load_all_membership_orders(
            squarespace=squarespace,
            membership_sku=membership_sku,
            order_params=dict(fulfillment_status=args.fulfillment_status),
        )

    for subscription_order in subscription_orders:
        line_items = subscription_order.get("lineItems", [])
        subscription_line_items = [i for i in line_items if i["sku"] == membership_sku]
        for subscription_line_item in subscription_line_items:

            fulfilled_on = None
            if fulfilled_on := subscription_order.get("fulfilledOn"):
                fulfilled_on = parse(fulfilled_on)

            membership = get_or_create(
                session=db_session,
                model=AnnualMembership,
                **dict(
                    order_id=subscription_order["id"],
                    order_number=subscription_order["orderNumber"],
                    channel=subscription_order["channel"],
                    channel_name=subscription_order["channelName"],
                    billing_address_first_name=subscription_order["billingAddress"][
                        "firstName"
                    ],
                    billing_address_last_name=subscription_order["billingAddress"][
                        "lastName"
                    ],
                    external_order_reference=subscription_order[
                        "externalOrderReference"
                    ],
                    created_on=parse(subscription_order["createdOn"]),
                    modified_on=parse(subscription_order["modifiedOn"]),
                    fulfilled_on=fulfilled_on,
                    customer_email=subscription_order["customerEmail"],
                    fulfillment_status=subscription_order["fulfillmentStatus"],
                    test_mode=subscription_order["testmode"],
                    line_item_id=subscription_line_item["id"],
                    sku=subscription_line_item["sku"],
                    variant_id=subscription_line_item["variantId"],
                    product_id=subscription_line_item["productId"],
                    product_name=subscription_line_item["productName"],
                ),
            )
            # db.session.add(membership)

    cursor_metadata = get_or_create(
        session=db_session,
        model=TableMetadata,
        **dict(
            table_name=AnnualMembership.__tablename__,
            attribute_name="last_run_start_time",
        ),
    )
    setattr(cursor_metadata, "attribute_value", str(start_time.timestamp()))
    db_session.commit()
    # db.session.merge()
    # breakpoint()

    # active_subscriptions = [s for s in subscriptions if s.is_active]
    # inactive_subscriptions = [s for s in subscriptions if not s.is_active]
    # logger.info(
    #     f"Stats: {len(subscriptions)=} / {len(active_subscriptions)=} / {len(inactive_subscriptions)=}"
    # )
    # breakpoint()
    # db = get_firestore_client()
    # memberships_ref = db.collection("memberships")
    # for subscription in subscriptions:
    #     # if subscription.customer_email != "jeff.hogan1@gmail.com":
    #     #     continue
    #     membership_ref = memberships_ref.document(subscription.id)
    #     # breakpoint()
    #     if membership_ref.get().exists:
    #         logger.debug(f"Updating firestore document for: {subscription.id=}")
    #     else:
    #         logger.debug(f"Creating firestore document for: {subscription.id=}")
    #         membership_ref.set(subscription.to_dict())
    #     # breakpoint()
