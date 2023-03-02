from member_card.db import db

from sqlalchemy.orm import relationship


class SlackUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    slack_id = db.Column(db.String)
    team_id = db.Column(db.String)
    name = db.Column(db.String)
    email = db.Column(db.String, nullable=True)
    deleted = db.Column(db.Boolean, nullable=False, default=False)
    color = db.Column(db.String)
    real_name = db.Column(db.String)
    tz = db.Column(db.String)
    tz_label = db.Column(db.String)
    tz_offset = db.Column(db.String)

    profile = db.Column(db.String)

    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_owner = db.Column(db.Boolean, nullable=False, default=False)
    is_primary_owner = db.Column(db.Boolean, nullable=False, default=False)
    is_restricted = db.Column(db.Boolean, nullable=False, default=False)
    is_ultra_restricted = db.Column(db.Boolean, nullable=False, default=False)
    is_bot = db.Column(db.Boolean, nullable=False, default=False)
    updated = db.Column(db.String)
    is_app_user = db.Column(db.Boolean, nullable=False, default=False)
    has_2fa = db.Column(db.Boolean, nullable=False, default=False)

    is_workflow_bot = db.Column(db.Boolean, nullable=False, default=False)
    is_invited_user = db.Column(db.Boolean, nullable=False, default=False)
    is_email_confirmed = db.Column(db.Boolean, nullable=False, default=False)

    who_can_share_contact_card = db.Column(db.String, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship(
        "User",
        back_populates="slack_user",
        uselist=False,
    )
