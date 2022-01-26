from os.path import abspath, dirname, join

from member_card.db import Model
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

BASE_DIR = abspath(join(dirname(abspath(__file__)), ".."))


class AppleDeviceRegistration(Model):
    id = Column(Integer, primary_key=True)
    device_library_identifier = Column(String(255), unique=True)
    push_token = Column(String(255))
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())
    membership_card_id = Column(Integer, ForeignKey("membership_cards.id"))
    m = relationship(
        "MembershipCard", backref=backref("apple_device_registrations", lazy="dynamic")
    )

    def __init__(self, device_library_identifier, push_token, p):
        self.device_library_identifier = device_library_identifier
        self.push_token = push_token
        self.p = p

    def __repr__(self):
        return "<Registration %s>" % self.device_library_identifier
