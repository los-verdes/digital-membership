import re
from collections import OrderedDict
from datetime import datetime, timedelta

from member_card.db import Model
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import relationship, backref

apple_pass_to_membership_assoc_table = Table(
    "apple_passes_to_memberships",
    Model.metadata,
    Column(
        "apple_pass_id",
        Integer,
        ForeignKey("apple_pass.id"),
        primary_key=True,
    ),
    Column(
        "annual_membership_id",
        Integer,
        ForeignKey("annual_membership.id"),
        primary_key=True,
    ),
)


class AnnualMembership(Model):
    __tablename__ = "annual_membership"

    one_year_ago = datetime.now() - timedelta(days=366)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="annual_memberships")
    apple_passes = relationship(
        "ApplePass",
        secondary=apple_pass_to_membership_assoc_table,
        lazy="subquery",
        backref=backref("annual_memberships", lazy=True),
    )

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
    test_mode = Column(Boolean, default=False)
    fulfillment_status = Column(
        Enum(
            "PENDING",
            "FULFILLED",
            "CANCELED",
            name="fulfillment_status_enum",
            create_type=False,
        )
    )

    def to_dict(self):
        return OrderedDict(
            order_number=self.order_number,
            created_on=self.created_on,
            email=self.customer_email,
            product_name=self.product_name,
            fulfilled_on=self.fulfilled_on,
            fulfillment_status=self.fulfillment_status,
            is_active=self.is_active,
            valid_until=self.expiry_date,
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

    @property
    def full_name(self):
        return f"{self.billing_address_first_name} {self.billing_address_last_name}"

    @property
    def is_canceled(self):
        return self.fulfillment_status == "CANCELED"

    @property
    def expiry_date(self):
        if not self.created_on:
            return None
        return self.created_on + timedelta(days=365)

    @property
    def is_active(self):
        if self.is_canceled:
            return False
        if not self.created_on:
            return False
        if self.created_on <= self.one_year_ago:
            return False

        return True
