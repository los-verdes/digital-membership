import logging
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import List
from zoneinfo import ZoneInfo

import requests
from bigcommerce.api import BigcommerceApi
from dateutil.parser import parse
from flask import current_app
from member_card.utils import sign
from member_card.db import db, get_or_update
from member_card.models import table_metadata
from member_card.models.user import ensure_user

logger = logging.getLogger(__name__)


def get_app_client_for_store() -> BigcommerceApi:
    # store = Store.query.filter(Store.store_hash == store_hash).one()
    store_hash = current_app.config["BIGCOMMERCE_STORE_HASH"]
    app_client = BigcommerceApi(
        client_id=current_app.config["BIGCOMMERCE_CLIENT_ID"],
        store_hash=store_hash,
        access_token=current_app.config["BIGCOMMERCE_ACCESS_TOKEN"],
    )
    logger.debug(f"{app_client=} generated for {store_hash=}")
    return app_client


def get_bespoke_client_for_store():
    store_hash = current_app.config["BIGCOMMERCE_STORE_HASH"]
    app_client = BiggercommerceApi(
        client_id=current_app.config["BIGCOMMERCE_CLIENT_ID"],
        store_hash=store_hash,
        access_token=current_app.config["BIGCOMMERCE_ACCESS_TOKEN"],
    )
    logger.debug(f"{app_client=} generated for {store_hash=}")
    return app_client


class BiggercommerceApi(object):
    """Bespoke implementation for routes not yet included in bigcommerce-api-python"""

    base_url = "https://api.bigcommerce.com/stores/{store_hash}"

    def __init__(self, client_id, store_hash, access_token):
        self.client_id = client_id
        self.store_hash = store_hash
        self.base_store_url = self.base_url.format(store_hash=store_hash)
        self._access_token = access_token

    def _perform_request(
        self, method: str, route: str, api_version="v2", **kwargs
    ) -> requests.Response:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Auth-Token": self._access_token,
        }

        url = f"{self.base_store_url}/{api_version}/{route}"
        logger.debug(
            f"BiggercommerceApi attempting {method} request to {url=} ({kwargs=})"
        )

        response = requests.request(
            method=method,
            headers=headers,
            url=url,
            **kwargs,
        )

        response.raise_for_status()
        return response

    def get_all_scripts(self):
        """https://developer.bigcommerce.com/api-reference/5cb1b616e2e42-get-all-scripts"""
        return self._perform_request(
            method="GET",
            route="content/scripts",
        )

    def create_a_script(self, name, src_filename, description="", channel_id=1):
        """https://developer.bigcommerce.com/api-reference/99ba5fd00ad56-create-a-script"""
        # src = url_for("static", filename=src_filename).replace('http://', 'https://')
        src = "https://gist.githubusercontent.com/jeffwecan/4e835a92ef29403fea1fb62e0fa79bd1/raw/d68748742c832461d4c756bda05759f8212636b4/bigcommerce_membership_card.js"
        payload = {
            "name": name,
            "description": description,
            "src": src,
            "auto_uninstall": True,
            "load_method": "defer",
            "location": "head",
            "kind": "src",
            "api_client_id": self.client_id,
            "consent_category": "functional",
            "enabled": True,
            "channel_id": 1,
            # Which set of pages the script should load on.
            # Please note that you need to have Checkout content scope to use all_pages and checkout.
            # The current visibility options are storefront, checkout, all_pages and order_confirmation. storefront:
            # All pages that are not checkout or order_confirmation.
            "visibility": "all_pages",
            #  An html string containing exactly one script tag. Only present if kind is script_tag.
            # "html": "string",
        }
        logger.debug(f"create_a_script(): {src=}")

        return self._perform_request(
            method="POST",
            route="content/scripts",
            json=payload,
        )

    def get_all_widgets(self):
        """https://developer.bigcommerce.com/api-reference/0eea5a1dfcd68-get-all-widgets"""
        return self._perform_request(
            method="GET",
            route="content/widgets",
        )

    def get_all_placements(self):
        """https://developer.bigcommerce.com/api-reference/bde8dee94a07b-get-all-placements"""
        return self._perform_request(
            method="GET",
            route="content/placements",
        )

    def create_a_placement(
        self, widget_uuid, template_file, region, entity_id=None, channel_id=1
    ):
        """https://developer.bigcommerce.com/api-reference/8b7c1518d4e8a-create-a-placement"""
        payload = {
            "widget_uuid": widget_uuid,
            "template_file": template_file,
            "channel_id": channel_id,
            # "entity_id": entity_id,
            "sort_order": 0,
            "region": region,
            "status": "active",
        }
        logger.debug(f"create_a_placement(): {payload=}")

        return self._perform_request(
            method="POST",
            route="content/placements",
            json=payload,
        )

    def update_a_placement(
        self,
        placement_uuid,
        template_file,
        widget_uuid,
        region,
        entity_id=None,
        channel_id=1,
    ):
        """https://developer.bigcommerce.com/api-reference/42ee529f48796-update-a-placement"""
        payload = {
            "widget_uuid": widget_uuid,
            "template_file": template_file,
            "channel_id": channel_id,
            # "entity_id": entity_id,
            "sort_order": 0,
            "region": region,
            "status": "active",
        }
        logger.debug(f"update_a_placement(): {payload=}")

        return self._perform_request(
            method="PUT",
            route=f"content/placements/{placement_uuid}",
            json=payload,
        )

    def delete_a_placement(
        self,
        placement_uuid,
    ):
        """https://developer.bigcommerce.com/api-reference/42ee529f48796-delete-a-placement"""

        return self._perform_request(
            method="DELETE",
            route=f"content/placements/{placement_uuid}",
        )

    def get_all_orders(
        self,
        min_date_created,
        max_date_created,
    ):
        """https://developer.bigcommerce.com/api-reference/82f91b58d0c98-get-all-orders"""

        payload = {
            "min_date_created": min_date_created,
            "max_date_created": max_date_created,
        }
        return self._perform_request(
            method="GET",
            route="orders",
            api_version="v2",
            data=payload,
        )


def insert_order_as_membership(order, order_products, membership_skus):
    from member_card.models import AnnualMembership

    membership_orders = []
    line_items = order_products
    # breakpoint()
    subscription_line_items = [i for i in line_items if i["sku"] in membership_skus]
    ignored_line_items = [i for i in line_items if i["sku"] not in membership_skus]
    logger.debug(f"{ignored_line_items=}")
    # customer_id = order['customer_id']
    for subscription_line_item in subscription_line_items:
        fulfillment_status = order["status"]
        # breakpoint()
        if order["date_shipped"] != "" and order["date_shipped"] is not None:
            fulfilled_on = parse(order["date_shipped"]).replace(tzinfo=timezone.utc)
        else:
            fulfilled_on = None

        # customer_email = order["customerEmail"]
        variant_id = None
        if subscription_line_item["product_options"]:
            variant_id = subscription_line_item["product_options"][0]["id"]

        customer_email = order["billing_address"]["email"].lower()

        membership_kwargs = dict(
            order_id=f'{order["id"]}_bc',
            order_number=f'{order["id"]}_{order["cart_id"]}',
            channel=order["channel_id"],
            channel_name=f'bigcommerce_{order["order_source"]}',
            billing_address_first_name=order["billing_address"]["first_name"],
            billing_address_last_name=order["billing_address"]["last_name"],
            external_order_reference=order["external_id"],
            created_on=parse(order["date_created"]).replace(tzinfo=timezone.utc),
            modified_on=parse(order["date_modified"]).replace(tzinfo=timezone.utc),
            fulfilled_on=fulfilled_on,
            customer_email=customer_email,
            fulfillment_status=fulfillment_status,
            test_mode=False,
            line_item_id=subscription_line_item["id"],
            sku=subscription_line_item["sku"],
            variant_id=variant_id,
            product_id=subscription_line_item["product_id"],
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


def parse_subscription_orders(bigcommerce_client, membership_skus, subscription_orders):
    # logger.info(f"{len(subscription_orders)=} retrieved from Bigcommerce...")

    # Loop over all the raw order data and do the ETL bits
    memberships = []
    for subscription_order in subscription_orders:
        # subscription_order['products'] = bigcommerce_client.OrderProducts.all(subscription_order['id'])
        # order_product_names = [p["name"] for p in subscription_order['products']]
        # if not any(p["sku"] in membership_skus for p in subscription_order['products']):
        #     logger.debug(
        #         f"{subscription_order['id']=} (#{subscription_order['orderNumber']}) DOES NOT INCLUDE {membership_skus=} in {order_product_names=}"
        #     )
        #     continue
        # logger.debug(
        #     f"#{order['orderNumber']} has no {membership_sku=} in {order_product_names=}"
        # )
        order = deepcopy(subscription_order)
        membership_orders = insert_order_as_membership(
            order=order,
            order_products=bigcommerce_client.OrderProducts.all(order["id"]),
            membership_skus=membership_skus,
        )
        for membership_order in membership_orders:
            db.session.add(membership_order)
        db.session.commit()
        memberships += membership_orders
    return memberships


def load_all_bigcommerce_orders(
    bigcommerce_client: BigcommerceApi, membership_skus: List[str]
):
    orders = load_orders(
        bigcommerce_client=bigcommerce_client,
        membership_skus=membership_skus,
    )

    memberships = parse_subscription_orders(bigcommerce_client, membership_skus, orders)

    return memberships


def load_single_order(
    bigcommerce_client: BigcommerceApi, membership_skus: List[str], order_id: str
):
    subscription_order = bigcommerce_client.Orders.get(order_id)
    logger.debug(f"API response for {order_id=}: {subscription_order=}")
    memberships = parse_subscription_orders(
        bigcommerce_client=bigcommerce_client,
        membership_skus=membership_skus,
        subscription_orders=[subscription_order],
    )
    logger.debug(f"After parsing subscription orders: {memberships=}")
    return memberships


def bigcommerce_orders_etl(
    bigcommerce_client: BigcommerceApi, membership_skus: List[str]
):
    from member_card import models

    etl_start_time = datetime.now(tz=ZoneInfo("UTC"))
    membership_table_name = models.AnnualMembership.__tablename__
    last_run_start_time = table_metadata.get_last_run_start_time(membership_table_name)
    last_run_start_time = last_run_start_time - timedelta(hours=12)
    modified_after = last_run_start_time.isoformat()
    modified_before = etl_start_time.isoformat()

    orders = load_orders(
        bigcommerce_client=bigcommerce_client,
        membership_skus=membership_skus,
        min_date_created=modified_after,
        max_date_created=modified_before,
    )

    memberships = parse_subscription_orders(bigcommerce_client, membership_skus, orders)

    table_metadata.set_last_run_start_time(membership_table_name, etl_start_time)

    return memberships


def load_orders(
    bigcommerce_client: BigcommerceApi,
    membership_skus: List[str],
    min_date_created=None,
    max_date_created=None,
    sort: str = "date_created:asc",
):
    # ) -> List[AnnualMembership]:
    # remove "None"s
    # all_orders = []
    # membership_orders = []

    get_orders_query_params = dict(
        min_date_created=min_date_created,
        max_date_created=max_date_created,
    )
    get_orders_query_params = {
        k: v for k, v in get_orders_query_params.items() if v is not None
    }

    logger.debug(
        f"load_membership_orders() => {bigcommerce_client.connection.store_hash=}"
    )
    logger.debug(f"load_membership_orders() => filter response with {membership_skus=}")
    logger.debug(
        f"load_membership_orders() => filter request with {get_orders_query_params=}"
    )
    logger.info("Starting retrieval of Bigcommerce orders now...")

    logger.debug(f"Grabbing all orders with {get_orders_query_params=}")
    orders = bigcommerce_client.Orders.iterall(**get_orders_query_params)

    return orders


def generate_webhook_token(api: BigcommerceApi):
    token_data = f"{api.connection.store_hash}.{api.connection.client_id}"
    return sign(token_data)
