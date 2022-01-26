from datetime import timedelta

from flask_login import UserMixin
from member_card.db import Model
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
    membership_cards = relationship("MembershipCard", back_populates="user")

    def to_dict(self):
        return dict(
            id=self.id,
            # TODO: figure out why we're not getting usernames set...
            # username=self.username,
            email=self.email,
            fullname=self.fullname,
            first_name=self.first_name,
            last_name=self.last_name,
            active=self.active,
        )

    def is_active(self):
        return self.active

    @property
    def has_active_memberships(self):
        if not self.annual_memberships:
            return False
        return any(m.is_active for m in self.annual_memberships)

    def has_memberships(self):
        return bool(self.annual_memberships)

    @property
    def latest_membership_card(self):
        if not self.membership_cards:
            return None
        return sorted(self.membership_cards, key=lambda x: x.time_created)[-1]

    @property
    def oldest_membership(self):
        if not self.annual_memberships:
            return None
        return sorted(self.annual_memberships, key=lambda x: x.created_on)[0]

    @property
    def newest_membership(self):
        if not self.annual_memberships:
            return None
        return sorted(self.annual_memberships, key=lambda x: x.created_on)[-1]

    @property
    def member_since(self):
        if not self.oldest_membership:
            return None
        return self.oldest_membership.created_on

    @property
    def membership_expiry(self):
        if not self.newest_membership:
            return None
        return self.newest_membership.created_on + timedelta(days=365)
