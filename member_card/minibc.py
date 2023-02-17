import json
import logging
from datetime import timezone
from time import sleep
from typing import TYPE_CHECKING

import requests
from dateutil.parser import parse

from member_card.db import db, get_or_update
from member_card.models import table_metadata
from member_card.models.user import ensure_user

# from member_card.models import MinibcWebhook, table_metadata

if TYPE_CHECKING:
    from requests import Response

api_baseurl = "https://apps.minibc.com/api/apps/recurring/v1"


logger = logging.getLogger(__name__)

# curl -X 'POST' \
#   'https://apps.minibc.com/api/apps/recurring/v1/products/search' \
#   -H 'accept: application/json' \
#   -H 'X-MBC-TOKEN: <TOKEN>' \
#   -H 'Content-Type: application/json' \
#   -d '{}'
# [
#   {
#     "id": 373087,
#     "store_product_id": 319,
#     "name": "Los Verdes Annual Membership",
#     "price": -1,
#     "thumbnail": "https://los-verdes.mybigcommerce.com/product_images/a/586/2022_Membership_Kit__25434.png",
#     "options": [],
#     "periodicity": {
#       "frequency": 1,
#       "unit": "year"
#     },
#     "grandfathered_price": False,
#     "billing_frequency": 1,
#     "in_stock": True,
#     "status": "active"
#   }
# ]


class Minibc(object):
    """Represents orders from a particular minibc store.

    :api_key:
        Your Minibc API key. Required.

    :api_baseurl:
        The baseuri for the Minibc API. You shouldn't need to change
        this.
    """

    def __init__(
        self,
        api_key,
        api_baseurl=api_baseurl,
    ):
        self.api_key = api_key
        self.api_baseurl = api_baseurl

        # Setup our HTTP session
        self.http = requests.Session()
        self.http.headers.update({"X-MBC-TOKEN": self.api_key})
        self.useragent = "Minibc python API by Los Verdes"
        self._next_page = None

    @property
    def useragent(self):
        """Get the current useragent."""
        return self._useragent

    @useragent.setter
    def useragent(self, agent_string):
        """Set the User-Agent that will be used."""
        self._useragent = agent_string
        self.http.headers.update({"User-Agent": self._useragent})

    def perform_request(self, method, path, **kwargs) -> "Response":
        """Retrieve an endpoint from the Minibc API."""
        url = f"{self.api_baseurl}/{path}"
        response = getattr(self.http, method)(url=url, **kwargs)

        # response.raise_for_status()
        # if 'application/json' == response.headers['Content-Type'].lower():
        #     return response_json
        # else:
        #     return response.text
        # if error := response_json.get('error'):
        #     raise MinibcError(error)
        return response

    def search_subscriptions(
        self,
        order_id=None,
        product_id=None,
        product_sku=None,
        starting_page=1,
        max_pages=200,
    ):
        subscription_search = {
            "order_id": order_id,
            "product_id": product_id,
            "store_product_id": None,
            "product_sku": product_sku,
            "store_customer_id": None,
            "customer_email": None,
            "active": None,
        }
        search_payload = {k: v for k, v in subscription_search.items() if v is not None}
        subscriptions = []
        # max_pages = 1
        ending_page = starting_page + max_pages + 1
        last_page_num = starting_page
        logger.debug(
            f"search_subscriptions() => starting to paginate subscriptions and such: {starting_page=} {ending_page=}"
        )
        for page_num in range(starting_page, ending_page):
            search_payload.update(dict(page=page_num))
            response = self.perform_request(
                method="post",
                path="subscriptions/search",
                json=search_payload,
            )
            last_page_num = page_num
            logger.debug(f"{page_num=}:: {response=}")
            subscriptions += response.json()
            logger.debug(f"{len(subscriptions)=}")
            # breakpoint()
            if response.status_code == 404:
                logger.warning(
                    "No subscriptions returned from Minibc... this is probably unexpected!"
                )
                # breakpoint()
                break
            try:
                response.raise_for_status()
            except Exception as err:
                logger.error(f"{err=}")
                break
            logger.debug(f"after {last_page_num=} sleeping for 5 seconds...")
            sleep(5)
        else:
            logger.debug(
                f"{max_pages=} reached ({len(subscriptions)=}, {starting_page=})"
            )
        # breakpoint()
        with open(f"subs_{last_page_num}.json", "w") as f:
            json.dump(subscriptions, f)
        return subscriptions, last_page_num

    def search_products(self):
        search_payload = dict()
        response = self.perform_request(
            method="post",
            path="products/search",
            json=search_payload,
        )
        breakpoint()
        return response

    def get_notification_webhooks(self):
        response = self.perform_request(
            method="get",
            path="notifications/webhooks",
        )
        response.raise_for_status()
        response_json = response.json()
        return response_json

    def get_profile_by_email(self, email):
        return self.get(path="profiles/", args=dict(filter=f"email,{email}"))


def insert_order_as_membership(order, skus):
    from member_card.models import AnnualMembership

    membership_orders = []
    products = order.get("products", [])
    subscription_line_items = [p for p in products if p["sku"] in skus]
    ignored_line_items = [p for p in products if p["sku"] not in skus]
    logger.debug(f"{ignored_line_items=}")
    for subscription_line_item in subscription_line_items:
        fulfilled_on = None
        if fulfilled_on := order.get("fulfilledOn"):
            fulfilled_on = parse(fulfilled_on).replace(tzinfo=timezone.utc)

        customer_email = order["customer"]["email"]
        logger.debug(f"{order=}")

        weird_dates_keys = [
            "created_time",
            "last_modified",
            "signup_date",
        ]
        weird_dates = {}
        for weird_dates_key in weird_dates_keys:
            order[weird_dates_key] = order[weird_dates_key].strip("-")
            if order[weird_dates_key] == "0":
                weird_dates[weird_dates_key] = None
            else:
                weird_dates[weird_dates_key] = parse(order[weird_dates_key]).replace(
                    tzinfo=timezone.utc
                )

        membership_kwargs = dict(
            order_id=f"minibc_{str(order['id'])}",
            order_number=f"minibc_{order['order_id'] or order['id']}_{order['customer']['store_customer_id']}",
            channel="minibc",
            channel_name="minibc",
            billing_address_first_name=order["customer"]["first_name"],
            billing_address_last_name=order["customer"]["last_name"],
            external_order_reference=order["customer"]["store_customer_id"],
            created_on=weird_dates["signup_date"],
            modified_on=weird_dates["last_modified"],
            fulfilled_on=fulfilled_on,
            customer_email=customer_email,
            fulfillment_status=None,
            test_mode=False,
            line_item_id=subscription_line_item["order_product_id"],
            sku=subscription_line_item["sku"],
            variant_id=subscription_line_item["name"],
            product_id=subscription_line_item["store_product_id"],
            product_name=subscription_line_item["name"],
        )
        membership = get_or_update(
            session=db.session,
            model=AnnualMembership,
            filters=["order_id"],
            kwargs=membership_kwargs,
        )
        membership_orders.append(membership)

        membership_user = ensure_user(
            email=membership.customer_email,
            first_name=membership.billing_address_first_name,
            last_name=membership.billing_address_last_name,
        )
        membership_user_id = membership_user.id
        if not membership.user_id:
            logger.debug(
                f"No user_id set for {membership=}! Setting to: {membership_user_id=}"
            )
            setattr(membership, "user_id", membership_user_id)
    return membership_orders


def parse_subscriptions(skus, subscriptions):
    logger.info(f"{len(subscriptions)=} retrieved from Minibc...")

    # Insert oldest orders first (so our internal membership ID generally aligns with order IDs...)
    subscriptions.reverse()

    # Loop over all the raw order data and do the ETL bits
    memberships = []
    for subscription in subscriptions:
        membership_orders = insert_order_as_membership(
            order=subscription,
            skus=skus,
        )
        for membership_order in membership_orders:
            db.session.add(membership_order)
        db.session.commit()
        memberships += membership_orders
    return memberships


def minibc_orders_etl(minibc_client: Minibc, skus, load_all):
    from member_card import models

    # etl_start_time = datetime.now(tz=ZoneInfo("UTC"))

    membership_table_name = models.AnnualMembership.__tablename__

    if not load_all:
        last_run_start_page = table_metadata.get_last_run_start_page(
            membership_table_name
        )
        logger.info(f"Starting sync from {last_run_start_page=}")
        subscriptions, last_page_num = minibc_client.search_subscriptions(
            product_sku=skus[0], starting_page=last_run_start_page
        )
    else:
        logger.info("Loading ALL subscriptions now...")
        subscriptions, last_page_num = minibc_client.search_subscriptions(
            product_sku=skus[0], starting_page=1, max_pages=3
        )
    # with open(f"subs_{last_page_num}.json", "r") as f:
    #     subscriptions = json.load(f)
    memberships = parse_subscriptions(skus, subscriptions)

    logging.debug(
        f"Setting last_run_start_page metadata on {membership_table_name=} to {last_page_num=}"
    )
    table_metadata.set_last_run_start_page(membership_table_name, last_page_num - 1)

    return memberships


def load_single_subscription(minibc_client: Minibc, skus, order_id):
    subscription_order, _ = minibc_client.search_subscriptions(order_id=order_id)
    logger.debug(f"API response for {order_id=}: {subscription_order=}")
    memberships = parse_subscriptions(
        skus=skus,
        subscriptions=[subscription_order],
    )
    logger.debug(f"After parsing subscription orders: {memberships=}")
    return memberships


class MinibcError(Exception):
    pass