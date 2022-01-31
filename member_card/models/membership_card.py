# from logzero import logger
import logging
import uuid
from base64 import b64encode as b64e
from datetime import datetime, timezone
from io import BytesIO, StringIO
from os.path import abspath, dirname, join

import qrcode
from member_card.db import db
from member_card.models.apple_device_registration import (
    membership_card_to_apple_device_assoc_table,
)
from member_card.models.annual_membership import (
    membership_card_to_membership_assoc_table,
)
from member_card.utils import sign
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from wallet.models import Barcode, BarcodeFormat, Generic, Pass

BASE_DIR = abspath(join(dirname(abspath(__file__)), ".."))
logger = logging.getLogger("member_card")


def hex2rgb(hex, alpha=None):
    """Convert a string to all caps."""
    if not hex.startswith("#"):
        return hex
    h = hex.lstrip("#")
    try:
        rgb = tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # noqa
    except Exception as err:
        logger.exception(f"unable to convert {hex=} to rgb: {err}")
        return h
    if alpha is None:
        return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
    else:
        return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"


def get_certificate_path(filename):
    return join(BASE_DIR, "certificates", filename)


class MembershipCard(db.Model):
    __tablename__ = "membership_cards"

    background_color = "#00B140"
    foreground_color = "#000000"

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

    passfile_files = {
        "icon.png": "LV_Tee_Crest_onVerde_rgb_filled_icon.png",
        "icon@2x.png": "LV_Tee_Crest_onVerde_rgb_filled_icon@2x.png",
        "logo.png": "LosVerdes_Logo_RGB_72_Horizontal_BlackOnTransparent_CityYear_logo.png",
        "logo@2x.png": "LosVerdes_Logo_RGB_300_Horizontal_BlackOnTransparent_CityYear_logo@2x.png",
    }

    @property
    def is_voided(self):
        return self.member_until < datetime.now()

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
    def qr_code_ascii(self):
        # qr_code = qrcode.make(self.qr_code_message)
        qr = qrcode.QRCode()
        qr.add_data(self.qr_code_message)
        with StringIO() as f:
            qr.print_ascii(out=f)
            f.seek(0)
            return f.read()

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
    def authentication_token_hex(self):
        return str(getattr(self.authentication_token, "hex"))

    def create_passfile(self):

        pass_info = Generic()
        pass_info.addPrimaryField("name", self.user.fullname, "Member Name")
        pass_info.addSecondaryField(
            "member_since", self.user.member_since.strftime("%b %Y"), "Member Since"
        )
        pass_info.addBackField(
            "member_expiry_back",
            self.user.membership_expiry.strftime("%b %d, %Y"),
            "Good through",
        )
        pass_info.addBackField(
            "serial_number",
            self.serial_number_hex,
            "Card #",
        )
        pass_kwargs = dict(
            passInformation=pass_info,
            passTypeIdentifier=self.apple_pass_type_identifier,
            organizationName=self.apple_organization_name,
            teamIdentifier=self.apple_team_identifier,
        )
        logger.debug(f"{pass_kwargs=}")
        passfile = Pass(**pass_kwargs)

        qr_code = Barcode(format=BarcodeFormat.QR, message=self.qr_code_message)

        passfile_attrs = dict(
            description="Los Verdes Membership Card",
            serialNumber=self.apple_pass_serial_number,
            backgroundColor=hex2rgb(self.background_color),
            foregroundColor=hex2rgb(self.foreground_color),
            logoText=self.logo_text,
            barcode=qr_code,
            webServiceURL=self.web_service_url,
            authenticationToken=sign(self.authentication_token_hex),
            expirationDate=self.apple_pass_expiry_timestamp,
            voided=self.is_voided,
            userInfo=self.user.to_dict(),
        )
        # logger.debug(f"{passfile_attrs=}")
        for attr_name, attr_value in passfile_attrs.items():
            if type(attr_value) == str:
                logger.debug(
                    f"Setting passfile attribute {attr_name} to: {attr_value[:3]=}...{attr_value[-2:]=}"
                )
            else:
                logger.debug(
                    f"Setting passfile attribute {attr_name} to: {attr_value=}"
                )
            setattr(
                passfile,
                attr_name,
                attr_value,
            )

        # Including the icon and logo is necessary for the passbook to be valid.
        static_dir = join(BASE_DIR, "static")
        for passfile_filename, local_filename in self.passfile_files.items():
            file_path = join(static_dir, local_filename)
            logger.debug(f"adding {file_path} as pass file: {passfile_filename}")
            passfile.addFile(passfile_filename, open(file_path, "rb"))

        return passfile

    def create_pkpass(self, key_filepath, key_password, pkpass_out_path=None):
        serial_number = self.id
        cert_filepath = get_certificate_path("certificate.pem")
        wwdr_cert_filepath = get_certificate_path("wwdr.pem")
        logger.debug(f"{cert_filepath=}")
        logger.debug(
            f"Creating passfile with {self.apple_pass_type_identifier=} {serial_number=} (Signing details: {cert_filepath=} {key_filepath=} {wwdr_cert_filepath=}"
        )
        passfile = self.create_passfile()
        pkpass_string_buffer = passfile.create(
            certificate=cert_filepath,
            key=key_filepath,
            wwdr_certificate=wwdr_cert_filepath,
            password=key_password,
            zip_file=pkpass_out_path,  # os.path.join(secrets_dir, "test.pkpass"),
        )
        if pkpass_out_path:
            return pkpass_out_path
        return pkpass_string_buffer
