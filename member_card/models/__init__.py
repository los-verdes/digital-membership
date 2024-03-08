# from member_card.db import Model  # Base, Table
from social_flask_sqlalchemy import models

from member_card.models.annual_membership import AnnualMembership
from member_card.models.apple_device_registration import AppleDeviceRegistration
from member_card.models.membership_card import MembershipCard
from member_card.models.slack_user import SlackUser
from member_card.models.squarespace_webhook import SquarespaceWebhook
from member_card.models.store import Store
from member_card.models.store_user import StoreUser
from member_card.models.subscription import Subscription
from member_card.models.table_metadata import TableMetadata
from member_card.models.user import Role, User

__all__ = (
    "AnnualMembership",
    "AppleDeviceRegistration",
    "MembershipCard",
    "User",
    "Role",
    "SlackUser",
    "SquarespaceWebhook",
    "Store",
    "StoreUser",
    "Subscription",
    "TableMetadata",
    "models",
)
