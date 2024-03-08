import logging
from datetime import timezone
from time import sleep
from typing import TYPE_CHECKING

import requests
from dateutil.parser import ParserError, parse

from member_card.db import db, get_or_update
from member_card.models import table_metadata

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
        email=None,
        page_num=1,
    ):
        subscription_search = {
            "order_id": order_id,
            "product_id": product_id,
            "store_product_id": None,
            "product_sku": product_sku,
            "store_customer_id": None,
            "customer_email": email,
            "active": None,
            "page": page_num,
        }
        search_payload = {k: v for k, v in subscription_search.items() if v is not None}
        subscriptions = []
        search_payload.update(dict(page=page_num))
        response = self.perform_request(
            method="post",
            path="subscriptions/search",
            json=search_payload,
        )
        logger.debug(f"{page_num=}:: {response=}")
        subscriptions += response.json()
        logger.debug(f"{len(subscriptions)=}")
        # breakpoint()
        if response.status_code == 404:
            logger.warning(
                "No subscriptions returned from Minibc... this is probably unexpected!"
            )
            # breakpoint()
            return None
        try:
            response.raise_for_status()
        except Exception as err:
            logger.error(f"{err=}")
            return None
        return subscriptions

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


def parse_subscriptions(subscriptions):
    logger.info(f"{len(subscriptions)=} retrieved from Minibc...")

    # Insert oldest orders first (so our internal membership ID generally aligns with order IDs...)
    subscriptions.reverse()

    # Loop over all the raw order data and do the ETL bits
    subscription_objs = []
    from member_card.models import Subscription

    for subscription in subscriptions:
        product_name = ",".join([p["name"] for p in subscription["products"]])
        shipping_address = " ".join(subscription["shipping_address"].values())
        subscription_kwargs = dict(
            subscription_id=subscription["id"],
            order_id=subscription["order_id"],
            customer_id=subscription["customer"]["id"],
            customer_first_name=subscription["customer"]["first_name"],
            customer_last_name=subscription["customer"]["last_name"],
            customer_email=subscription["customer"]["email"],
            product_name=product_name,
            status=subscription["status"],
            shipping_address=shipping_address,
            signup_date=parse_weird_dates(subscription["signup_date"]),
            pause_date=parse_weird_dates(subscription["pause_date"]),
            cancellation_date=parse_weird_dates(subscription["cancellation_date"]),
            next_payment_date=parse_weird_dates(subscription["next_payment_date"]),
            created_time=parse_weird_dates(subscription["created_time"]),
            last_modified=parse_weird_dates(subscription["last_modified"]),
        )
        subscription_obj = get_or_update(
            session=db.session,
            model=Subscription,
            filters=["subscription_id"],
            kwargs=subscription_kwargs,
        )
        subscription_objs.append(subscription_obj)

    for subscription_obj in subscription_objs:
        db.session.add(subscription_obj)
    db.session.commit()
    return subscription_objs


def find_missing_shipping(minibc_client: Minibc, skus):
    start_page_num = 1
    max_pages = 1000

    missing_shipping_subs = list()
    inactive_missing_shipping_subs = list()

    last_page_num = start_page_num
    end_page_num = start_page_num + max_pages + 1

    logger.debug(
        f"find_missing_shipping() => starting to paginate subscriptions and such: {start_page_num=} {end_page_num=}"
    )
    total_subs_num = 0
    total_subs_missing_shipping = 0
    total_inactive_subs_missing_shipping = 0
    for page_num in range(start_page_num, end_page_num):
        logger.info(f"Sync at {page_num=}")
        subscriptions = minibc_client.search_subscriptions(
            product_sku=skus[0],
            page_num=page_num,
        )
        if subscriptions is None:
            logger.debug(
                f"find_missing_shipping() => {last_page_num=} returned no results!. Setting `last_page_num` back to 1"
            )
            last_page_num = 1
            break

        last_page_num = page_num
        for subscription in subscriptions:
            if subscription["shipping_address"]["street_1"] == "":
                logger.debug(
                    f"{subscription['customer']['email']} has no shipping address set!"
                )
                if subscription["status"] == "inactive":
                    inactive_missing_shipping_subs.append(subscriptions)
                missing_shipping_subs.append(subscription)

        logger.debug(
            f"find_missing_shipping() => after {page_num=} sleeping for 1 second..."
        )
        total_subs_num += len(subscriptions)
        total_subs_missing_shipping = len(missing_shipping_subs)
        total_inactive_subs_missing_shipping = len(inactive_missing_shipping_subs)
        logger.debug(
            f"{total_subs_num=}:: {total_subs_missing_shipping=} ({total_inactive_subs_missing_shipping=})"
        )
        sleep(1)

    logger.debug(
        f"{total_subs_num=}:: {total_subs_missing_shipping=} ({total_inactive_subs_missing_shipping=})"
    )
    return missing_shipping_subs


def parse_weird_dates(date_str):
    date_str = date_str.strip("-")
    if date_str == "0":
        return None

    try:
        return parse(date_str).replace(tzinfo=timezone.utc)
    except ParserError as err:
        logger.warning(f"Unable to parse {date_str}: {err=}")
        return None


def minibc_subscriptions_etl(minibc_client: Minibc, skus, load_all=False):
    from member_card import models

    subscriptions_table_name = models.Subscription.__tablename__

    if load_all:
        start_page_num = 1
        max_pages = 1000
    else:
        start_page_num = table_metadata.get_last_run_start_page(
            subscriptions_table_name
        )
        max_pages = 20

    subscription_objs = list()

    last_page_num = start_page_num
    end_page_num = start_page_num + max_pages + 1

    logger.debug(
        f"search_subscriptions() => starting to paginate subscriptions and such: {start_page_num=} {end_page_num=}"
    )

    for page_num in range(start_page_num, end_page_num):
        logger.info(f"Sync at {page_num=}")
        subscriptions = minibc_client.search_subscriptions(
            product_sku=skus[0],
            page_num=page_num,
        )
        if subscriptions is None:
            logger.debug(
                f"{last_page_num=} returned no results!. Setting `last_page_num` back to 1"
            )
            last_page_num = 1
            break

        last_page_num = page_num
        subscription_objs += parse_subscriptions(subscriptions)
        logger.debug(f"after {page_num=} sleeping for 1 second...")
        sleep(1)

    if not load_all:
        logger.debug(
            f"Setting start_page_num metadata on {subscriptions_table_name=} to {last_page_num=}"
        )
        table_metadata.set_last_run_start_page(
            subscriptions_table_name, max(1, last_page_num - 1)
        )

    return subscription_objs


def load_single_subscription(minibc_client: Minibc, skus, order_id):
    subscription_order = minibc_client.search_subscriptions(order_id=order_id)
    logger.debug(f"API response for {order_id=}: {subscription_order=}")
    memberships = parse_subscriptions(
        skus=skus,
        subscriptions=[subscription_order],
    )
    logger.debug(f"After parsing subscription orders: {memberships=}")
    return memberships


class MinibcError(Exception):
    pass
