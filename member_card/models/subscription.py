import logging

from member_card.db import db

logger = logging.getLogger(__name__)


class Subscription(db.Model):
    __tablename__ = "subscription"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subscription_id = db.Column(db.Integer)
    order_id = db.Column(db.Integer)
    customer_id = db.Column(db.String(32))
    customer_first_name = db.Column(db.String(64))
    customer_last_name = db.Column(db.String(64))
    customer_email = db.Column(db.String(120))
    product_name = db.Column(db.String(200))
    status = db.Column(db.String(12))
    shipping_address = db.Column(db.Text())
    signup_date = db.Column(db.DateTime)
    pause_date = db.Column(db.DateTime)
    cancellation_date = db.Column(db.DateTime)
    next_payment_date = db.Column(db.DateTime)
    created_time = db.Column(db.DateTime)
    last_modified = db.Column(db.DateTime)
