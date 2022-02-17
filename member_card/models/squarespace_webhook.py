from member_card.db import db
from sqlalchemy.dialects.postgresql import JSON


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

    def to_dict(self):
        return dict(
            id=self.id,
            webhook_id=self.webhook_id,
            account_id=self.account_id,
            website_id=self.website_id,
            endpoint_url=self.endpoint_url,
            topics=self.topics,
            secret=self.secret,
            created_on=self.created_on,
            updated_on=self.updated_on,
        )
