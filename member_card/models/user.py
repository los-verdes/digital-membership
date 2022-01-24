from datetime import timedelta

from flask_login import UserMixin
from member_card.db import Model
from member_card.models import AnnualMembership
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship


class User(Model, UserMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(200))
    email = Column(String(200), unique=True)
    fullname = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    active = Column(Boolean, default=True)
    annual_memberships = relationship("AnnualMembership", back_populates="user")
    apple_passes = relationship("ApplePass", back_populates="user")

    def to_dict(self):
        return dict(
            id=self.id,
            username=self.username,
            email=self.email,
            fullname=self.fullname,
            first_name=self.first_name,
            last_name=self.last_name,
            active=self.active,
        )

    def is_active(self):
        return self.active

    def has_memberships(self):
        return bool(self.annual_memberships)

    @property
    def member_since(self):
        if not self.annual_memberships:
            return None
        return sorted(self.annual_memberships, key=lambda x: x.created_on)[-1].created_on

    @property
    def membership_expiry(self):
        if not self.has_memberships:
            return None
        return sorted(self.annual_memberships, key=lambda x: x.created_on)[0].created_on
