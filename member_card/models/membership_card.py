# from logzero import logger
import logging
import uuid
from base64 import b64encode as b64e
from datetime import datetime, timezone
from io import BytesIO, StringIO

import flask
import qrcode
from member_card.db import db, get_or_create
from member_card.models.annual_membership import (
    membership_card_to_membership_assoc_table,
)
from member_card.models.apple_device_registration import (
    membership_card_to_apple_device_assoc_table,
)
from member_card.utils import sign
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

logger = logging.getLogger("member_card")


def get_or_create_membership_card(user):
    app = flask.current_app
    base_url = app.config["BASE_URL"]
    web_service_url = f"{base_url}/passkit"
    membership_card = get_or_create(
        session=db.session,
        model=MembershipCard,
        user_id=user.id,
        apple_organization_name=app.config["APPLE_DEVELOPER_TEAM_ID"],
        apple_pass_type_identifier=app.config["APPLE_DEVELOPER_PASS_TYPE_ID"],
        apple_team_identifier=app.config["APPLE_DEVELOPER_TEAM_ID"],
        member_since=user.member_since,
        member_until=user.membership_expiry,
        web_service_url=web_service_url,
    )
    db.session.add(membership_card)
    db.session.commit()

    # TODO: do this more efficient like:
    if not membership_card.qr_code_message:
        logger.debug("generating QR code for message")
        serial_number = str(membership_card.serial_number)
        qr_code_signature = sign(serial_number)
        verify_pass_url = (
            f"{base_url}/verify-pass/{serial_number}?signature={qr_code_signature}"
        )
        qr_code_message = f"Content: {verify_pass_url}"
        logger.debug(f"{qr_code_message=}")
        setattr(membership_card, "qr_code_message", qr_code_message)
        db.session.add(membership_card)
        db.session.commit()

    return membership_card


class MembershipCard(db.Model):
    __tablename__ = "membership_cards"

    _google_pay_jwt = None

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, unique=True)
    serial_number = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship(
        "User",
        back_populates="membership_cards",
        cascade="all, delete",
        passive_deletes=True,
    )

    annual_memberships = relationship(
        "AnnualMembership",
        secondary=membership_card_to_membership_assoc_table,
        back_populates="membership_cards",
        lazy="dynamic",
    )

    # Card metadata:
    time_created = db.Column(db.DateTime(timezone=True), server_default=func.now())
    time_updated = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    member_since = db.Column(db.DateTime)
    member_until = db.Column(db.DateTime)

    # Apple Developer details:
    apple_pass_type_identifier = db.Column(db.String)
    apple_organization_name = db.Column(db.String)
    apple_team_identifier = db.Column(db.String)

    apple_device_registrations = relationship(
        "AppleDeviceRegistration",
        secondary=membership_card_to_apple_device_assoc_table,
        back_populates="membership_cards",
        lazy="dynamic",
    )

    # Passkit bits:
    web_service_url = db.Column(db.String)
    authentication_token = db.Column(UUID(as_uuid=True), default=uuid.uuid4)
    qr_code_message = db.Column(db.String)

    # Display related attributes:
    logo_text = db.Column(db.String, default="Los Verdes")

    @property
    def google_pass_save_url(self):
        return f"https://pay.google.com/gp/v/save/{self.google_pay_jwt}"

    @property
    def google_pay_jwt(self):
        if self._google_pay_jwt is not None:
            return self._google_pay_jwt
        from member_card.gpay import generate_pass_jwt

        google_pay_jwt = generate_pass_jwt(self)
        self._google_pay_jwt = google_pay_jwt.decode("UTF-8")
        return self._google_pay_jwt

    @property
    def icon_uri(self):
        from flask import current_app

        return f"{current_app.config['STATIC_ASSET_BASE_URL']}/{self.icon}"

    @property
    def is_voided(self):
        return self.member_until < datetime.now()

    @property
    def google_pass_start_timestamp(self):
        start_dt = self.member_since
        start_dt = start_dt.replace(tzinfo=timezone.utc)
        return start_dt.isoformat()

    @property
    def google_pass_expiry_timestamp(self):
        expiry_dt = self.member_until
        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        return expiry_dt.isoformat()

    @property
    def apple_pass_expiry_timestamp(self):
        expiry_dt = self.member_until
        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        return expiry_dt.isoformat()

    @property
    def apple_pass_serial_number(self):
        return str(getattr(self.serial_number, "int"))

    @property
    def serial_number_hex(self):
        return str(getattr(self.serial_number, "hex"))

    @property
    def qr_code_b64_png(self):
        qr = qrcode.QRCode()
        qr.add_data(self.qr_code_message)
        img = qr.make_image(back_color="transparent")
        with BytesIO() as f:
            getattr(img, "save")(f, "PNG")
            f.seek(0)
            return b64e(f.read()).decode()

    @property
    def qr_code_ascii(self):
        qr = qrcode.QRCode()
        qr.add_data(self.qr_code_message)
        f = StringIO()
        qr.print_ascii(out=f)
        f.seek(0)
        return f.read()

    @property
    def authentication_token_hex(self):
        return str(getattr(self.authentication_token, "hex"))
