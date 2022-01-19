from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.parser import parse
from logzero import logger


class AnnualMembership(object):
    subscription_product_names = [
        "Los Verdes Membership 2021",
        "Los Verdes Annual Membership",
        "Los Verdes Membership",
        "Los Verdes Membership (auto-renewal)",
    ]
    one_year_ago = datetime.now(tz=ZoneInfo("UTC")) - timedelta(days=366)

    def __init__(self, order):
        self._order = order
        # self.created_on = parse(self._order["createdOn"])
        # self.modified_on = parse(self._order["createdOn"])
        if "email" in order:
            self.email = order["email"]
        else:
            self.email = getattr(self, "customer_email")
        # self.fulfillment_status = getattr(self, "fulfillment_status")

    @staticmethod
    def from_dict(source):
        return AnnualMembership(source)

    def to_dict(self):
        return dict(
            id=self.id,
            name=self.name,
            email=self.email,
            order_number=self.order_number,
            created_on=self.created_on,
            modified_on=self.modified_on,
            fulfilled_on=self.get("fulfilled_on"),
            fulfillment_status=self.fulfillment_status,
            is_active=self.is_active,
            is_canceled=self.is_canceled,
            sku=self.sku,
            variant_id=self.variant_id,
            product_id=self.product_id,
            test_mode=self.testmode,
        )

    def __repr__(self):
        return f"AnnualSubscription(\
                id={self.id}, \
                order_number={self.order_number}, \
                name={self.name}, \
                email={self.email}, \
                created_on={self.created_on}, \
                modified_on={self.modified_on}, \
                fulfillment_status={self.fulfillment_status}, \
                is_active={self.is_active}, \
                is_canceled={self.is_canceled}\
            )"

    def get(self, key, default=None):
        getattr(self, key, default)

    def __getattr__(self, key):
        if key in self._order:
            value = self._order[key]
            if key.endswith("On"):
                value = parse(value)
            logger.debug(f"found {key=} with {value=}")
            return value
        # convert key from snake to camel case
        components = key.split("_")
        # via: https://stackoverflow.com/a/19053800
        # We capitalize the first letter of each component except the first one
        # with the 'title' method and join them together.
        camel_key = components[0] + "".join(x.title() for x in components[1:])
        if camel_key in self._order:
            value = self._order[camel_key]
            if key.endswith("_on"):
                value = parse(value)
            logger.debug(f"found {camel_key=} with {value=}")
            return value

        raise AttributeError(f"no {key=} in <AnnualSubscription _order... >")

    @property
    def id(self):
        return self._order["id"]

    @property
    def name(self):
        return f"{self._order['billingAddress']['firstName']} {self._order['billingAddress']['lastName']}"

    @property
    def subscription_line_items(self):
        return [
            i
            for i in self._order["lineItems"]
            if i["productName"] in self.subscription_product_names
        ]

    @property
    def sku(self):
        return self.subscription_line_items[0]["sku"]

    @property
    def variant_id(self):
        return self.subscription_line_items[0]["variantId"]

    @property
    def product_id(self):
        return self.subscription_line_items[0]["productId"]

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
