from member_card.db import db
from sqlalchemy.types import JSON


class SquarespaceWebhook(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    webhook_id = db.Column(db.String, primary_key=True)
    account_id = db.Column(db.String)
    website_id = db.Column(db.String, nullable=True)
    endpoint_url = db.Column(db.String)
    topics = db.Column(JSON)
    secret = db.Column(db.String)
    created_on = db.Column(db.DateTime)
    updated_on = db.Column(db.DateTime)
