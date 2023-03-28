import logging
import re
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

from dateutil.parser import parse
from member_card.db import db
from sqlalchemy.orm import relationship

logger = logging.getLogger(__name__)


membership_card_to_membership_assoc_table = db.Table(
    "membership_cards_to_memberships",
    db.Model.metadata,
    db.Column(
        "membership_card_id",
        db.Integer,
        db.ForeignKey("membership_cards.id"),
        primary_key=True,
    ),
    db.Column(
        "annual_membership_id",
        db.Integer,
        db.ForeignKey("annual_membership.id"),
        primary_key=True,
    ),
)


class AnnualMembership(db.Model):
    __tablename__ = "annual_membership"

    one_year_ago = (datetime.utcnow() - timedelta(days=366)).replace(
        tzinfo=timezone.utc
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship(
        "User", back_populates="annual_memberships", cascade="save-update"
    )
    membership_cards = relationship(
        "MembershipCard",
        secondary=membership_card_to_membership_assoc_table,
        lazy="subquery",
        back_populates="annual_memberships",
    )
    order_id = db.Column(db.String(32), unique=True)
    order_number = db.Column(db.String, unique=True)
    channel = db.Column(db.String(32))
    channel_name = db.Column(db.String(32))
    billing_address_first_name = db.Column(db.String(64))
    billing_address_last_name = db.Column(db.String(64))
    channel_name = db.Column(db.String(64))
    external_order_reference = db.Column(db.String(32), nullable=True)
    created_on = db.Column(db.DateTime, nullable=False)
    modified_on = db.Column(db.DateTime)
    fulfilled_on = db.Column(db.DateTime, nullable=True)
    customer_email = db.Column(db.String(120))
    line_item_id = db.Column(db.String(32))
    sku = db.Column(db.String(20))
    variant_id = db.Column(db.String(36))
    product_id = db.Column(db.String(32))
    product_name = db.Column(db.String(200))
    test_mode = db.Column(db.Boolean, default=False)
    fulfillment_status = db.Column(db.String(32))

    def to_dict(self):
        return OrderedDict(
            order_number=self.order_number,
            created_on=None if not self.created_on else self.created_on.strftime("%c"),
            email=self.customer_email,
            product_name=self.product_name,
            fulfilled_on=None
            if not self.fulfilled_on
            else self.fulfilled_on.strftime("%c"),
            fulfillment_status=str(self.fulfillment_status),
            is_active=self.is_active,
            valid_until=None
            if not self.expiry_date
            else self.expiry_date.strftime("%c"),
        )

    def __repr__(self):
        return re.sub(
            " +",
            " ",
            f"<AnnualMembership(\
                id={self.id}, \
                order_number={self.order_number}, \
                name={self.billing_address_first_name} {self.billing_address_last_name}, \
                email={self.customer_email}, \
                created_on={self.created_on}, \
                modified_on={self.modified_on}, \
                fulfillment_status={self.fulfillment_status}, \
                is_active={self.is_active}, \
                is_canceled={self.is_canceled}\
            ) />",
        )

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

        # TODO: figure out whats going down here...
        created_on = self.created_on
        if isinstance(created_on, str):
            created_on = parse(created_on)
        if created_on.tzinfo is None:
            created_on = created_on.replace(tzinfo=timezone.utc)
        if created_on <= self.one_year_ago:
            return False

        return True
