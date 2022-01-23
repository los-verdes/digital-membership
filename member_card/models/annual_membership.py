import re
from collections import OrderedDict
from datetime import datetime, timedelta

from member_card.utils import get_db_session
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

# from zoneinfo import ZoneInfo

Base = declarative_base()
Base.query = get_db_session().query_property()

# class AnnualMembership(object):


class AnnualMembership(Base):
    __tablename__ = "annual_membership"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(32), unique=True)
    order_number = Column(String, unique=True)
    channel = Column(String(32))
    channel_name = Column(String(32))
    billing_address_first_name = Column(String(64))
    billing_address_last_name = Column(String(64))
    channel_name = Column(String(64))
    external_order_reference = Column(String(32), nullable=True)
    created_on = Column(DateTime)
    modified_on = Column(DateTime)
    fulfilled_on = Column(DateTime, nullable=True)
    customer_email = Column(String(120))
    line_item_id = Column(String(32))
    sku = Column(String(20))
    variant_id = Column(String(36))
    product_id = Column(String(32))
    product_name = Column(String(200))
    fulfillment_status = Column(String)
    #     Enum(
    #         "PENDING",
    #         "FULFILLED",
    #         "CANCELED",
    #         name="fulfillment_status_enum",
    #         create_type=False,
    #     )
    # )
    test_mode = Column(Boolean, default=False)

    #         id=self.id,
    #         name=self.name,
    #         email=self.email,
    #         order_number=self.order_number,
    #         created_on=self.created_on,
    #         modified_on=self.modified_on,
    #         fulfilled_on=self.fulfilled_on,
    #         fulfillment_status=self.fulfillment_status,
    #         is_active=self.is_active,
    #         is_canceled=self.is_canceled,
    #         line_items=json.dumps(self.line_items),
    #         test_mode=self.test_mode,

    # one_year_ago = datetime.now(tz=ZoneInfo("UTC")) - timedelta(days=366)
    one_year_ago = datetime.now() - timedelta(days=366)
    # @classmethod
    # def from_squarespace_order(order)

    # @staticmethod
    # def from_dict(source):
    #     source['line_items'] = json.loads(source['line_items'])
    #     return AnnualMembership(**source)

    def to_dict(self):
        return OrderedDict(
            # id=self.id,
            # name=self.name,
            order_number=self.order_number,
            created_on=self.created_on,
            email=self.customer_email,
            product_name=self.product_name,
            # modified_on=self.modified_on,
            fulfilled_on=self.fulfilled_on,
            fulfillment_status=self.fulfillment_status,
            is_active=self.is_active,
            # is_canceled=self.is_canceled,
            # line_items=json.dumps(self.line_items),
            # test_mode=self.test_mode,
        )

    def __repr__(self):
        return re.sub(
            " +",
            " ",
            f"AnnualSubscription(\
                id={self.id}, \
                order_number={self.order_number}, \
                name={self.billing_address_first_name} {self.billing_address_last_name}, \
                email={self.customer_email}, \
                created_on={self.created_on}, \
                modified_on={self.modified_on}, \
                fulfillment_status={self.fulfillment_status}, \
                is_active={self.is_active}, \
                is_canceled={self.is_canceled}\
            )",
        )

    # # def __getattr__(self, key):
    # #     if key in self._order:
    # #         value = self._order[key]
    # #         if key.endswith("On"):
    # #             value = parse(value)
    # #         logger.debug(f"found {key=} with {value=}")
    # #         return value
    # #     # convert key from snake to camel case
    # #     components = key.split("_")
    # #     # via: https://stackoverflow.com/a/19053800
    # #     # We capitalize the first letter of each component except the first one
    # #     # with the 'title' method and join them together.
    # #     camel_key = components[0] + "".join(x.title() for x in components[1:])
    # #     if camel_key in self._order:
    # #         value = self._order[camel_key]
    # #         if key.endswith("_on"):
    # #             value = parse(value)
    # #         logger.debug(f"found {camel_key=} with {value=}")
    # #         return value

    # #     raise AttributeError(f"no {key=} in <AnnualSubscription _order... >")

    @property
    def full_name(self):
        return f"{self.billing_address_first_name} {self.billing_address_last_name}"

    @property
    def is_canceled(self):
        return self.fulfillment_status == "CANCELED"

    @property
    def is_active(self):
        if self.is_canceled:
            return False
        if not self.created_on:
            return False
        if self.created_on <= self.one_year_ago:
            return False

        return True
