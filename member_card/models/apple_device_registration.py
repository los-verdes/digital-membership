from os.path import abspath, dirname, join

from member_card.db import db
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

BASE_DIR = abspath(join(dirname(abspath(__file__)), ".."))


membership_card_to_apple_device_assoc_table = db.Table(
    "membership_cards_to_apple_device",
    db.Model.metadata,
    db.Column(
        "membership_card_id",
        db.Integer,
        db.ForeignKey("membership_cards.id"),
        primary_key=True,
    ),
    db.Column(
        "apple_device_registration_id",
        db.Integer,
        db.ForeignKey("apple_device_registration.id"),
        primary_key=True,
    ),
)


class AppleDeviceRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_library_identifier = db.Column(db.String(255), unique=True)
    push_token = db.Column(db.String(255))
    time_created = db.Column(db.DateTime(timezone=True), server_default=func.now())
    time_updated = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    membership_card_id = db.Column(db.Integer, db.ForeignKey("membership_cards.id"))
    membership_card = relationship(
        "MembershipCard",
        back_populates="apple_device_registrations",
    )
    membership_cards = relationship(
        "MembershipCard",
        secondary=membership_card_to_apple_device_assoc_table,
        lazy="subquery",
        back_populates="apple_device_registrations",
    )

    # def __init__(self, device_library_identifier, push_token, membership_card):
    #     self.device_library_identifier = device_library_identifier
    #     self.push_token = push_token
    #     self.membership_card = membership_card

    def __repr__(self):
        return "<Registration %s>" % self.device_library_identifier
