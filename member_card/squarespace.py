from typing import TYPE_CHECKING

import requests

# from logzero import logger
import logging

if TYPE_CHECKING:
    from collections.abc import Iterable

__VERSION__ = "0.0.4"
api_baseurl = "https://api.squarespace.com"
api_version = "1.0"


class SquarespaceError(Exception):
    pass


class Squarespace(object):
    """Represents orders from a particular squarespace store.

    :api_key:
        Your Squarespace API key. Required.

    :api_baseurl:
        The baseuri for the Squarespace API. You shouldn't need to change
        this.

    :api_version:
        The version of the Squarespace API to target. If you change this
        without making any code changes you may break this library.
    """

    def __init__(
        self,
        api_key,
        api_baseurl=api_baseurl,
        api_version=api_version,
    ):
        self.api_key = api_key
        self.api_baseurl = api_baseurl
        self.api_version = api_version

        # Setup our HTTP session
        self.http = requests.Session()
        self.http.headers.update({"Authorization": "Bearer " + self.api_key})
        self.useragent = "Squarespace python API v%s by Zach White." % __VERSION__
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

    def post(self, path, object):
        """Post an `object` to the Squarespace API.

        :object:
            A dictionary containing JSON compatible key/value combinations.
        """
        url = "%s/%s/%s" % (self.api_baseurl, self.api_version, path)
        # logging.debug("url:%s object:%s", url, object)
        return self.process_request(self.http.post(url, json=object))

    def get(self, path, args=None) -> dict:
        """Retrieve an endpoint from the Squarespace API."""
        if not args:
            args = {}

        url = "%s/%s/%s" % (self.api_baseurl, self.api_version, path)
        # logging.debug("url:%s args:%s", url, args)
        return self.process_request(self.http.get(url, params=args))

    def process_request(self, request) -> dict:
        """Process a request and return the data."""
        if request.status_code in [200, 201]:
            return request.json()
        elif request.status_code == 204:
            return dict()
        elif request.status_code == 401:
            raise ValueError("The API key %s is not valid.", self.api_key)
        elif 200 < request.status_code < 299:
            logging.warning("Squarespace success response %s:", request.status_code)
            logging.warning(request.text)
            raise NotImplementedError(
                "Squarespace sent us a success response we're not prepared for!"
            )

        logging.error("Squarespace error response %s:", request.status_code)
        logging.error("URL: %s", request.url)
        logging.error(request.text)

        if 400 <= request.status_code < 499:
            raise RuntimeError("Squarespace thinks this request is bogus")
        if 500 <= request.status_code < 599:
            raise RuntimeError("Squarespace is having problems, try later.")

        raise RuntimeError("An unknown error occurred fetching your request.")

    def get_profile_by_email(self, email):
        return self.get(path="profiles/", args=dict(filter=f"email,{email}"))

    def order(self, order_id=None, order_number=None):
        """Retrieve a single order."""
        if order_id:
            return self.get("commerce/orders/" + order_id)
        elif order_number:
            for order in self.all_orders():
                if order["orderNumber"] == order_number:
                    return order
        else:
            raise SquarespaceError(
                "You must specify one of `order_id` or `order_number`"
            )

    def orders(self, **args):
        """Retrieve the 20 latest orders, by modification date."""
        uri = "commerce/orders"

        result = self.get(uri, args)
        self._next_page = (
            result["pagination"]["nextPageCursor"]
            if "nextPageCursor" in result["pagination"]
            else None
        )
        # breakpoint()
        return result["result"]

    def next_page(self) -> "Iterable":
        """Retrieve the next 20 orders, or None if there are no more orders."""
        return self.orders(cursor=self._next_page) if self._next_page else iter([])

    def all_orders(self, **args):
        orders = self.orders(**args)
        for order in orders:
            yield order

        count = 0
        while self._next_page:
            count += 1
            for order in self.next_page():
                yield order

    def load_membership_orders_datetime_window(
        self,
        membership_skus,
        modified_before=None,
        modified_after=None,
    ):
        # ) -> List[AnnualMembership]:
        order_params = dict(
            modifiedAfter=modified_after,
            modifiedBefore=modified_before,
        )

        return self.load_all_membership_orders(
            membership_skus, order_params=order_params
        )

    def load_all_membership_orders(self, membership_skus, order_params=None):
        # ) -> List[AnnualMembership]:
        # remove "None"s
        if order_params is None:
            order_params = {}
        order_params = {k: v for k, v in order_params.items() if v is not None}

        all_orders = []
        membership_orders = []

        logging.debug(f"Grabbing all orders with {order_params=}")

        for order in self.all_orders(**order_params):
            all_orders.append(order)

            order_product_names = [i["productName"] for i in order["lineItems"]]
            if any(i["sku"] in membership_skus for i in order["lineItems"]):
                logging.debug(
                    f"{order['id']=} (#{order['orderNumber']}) includes {i['sku']} ({membership_skus=}) in {order_product_names=}"
                )
                membership_orders.append(order)
                continue
            # logging.debug(
            #     f"#{order['orderNumber']} has no {membership_sku=} in {order_product_names=}"
            # )

        logging.debug(
            f"{len(all_orders)=} loaded with {len(membership_orders)=} and whatnot"
        )
        return membership_orders
