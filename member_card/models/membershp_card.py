import uuid
from os.path import abspath, dirname, join

from logzero import logger
from member_card.db import Model
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from wallet.models import Barcode, BarcodeFormat, Generic, Pass

BASE_DIR = abspath(join(dirname(abspath(__file__)), ".."))


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


class MembershipCard(Model):
    __tablename__ = "membership_cards"

    background_color = "#00B140"
    foreground_color = "#000000"

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    serial_number = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship(
        "User",
        back_populates="membership_cards",
        cascade="all, delete",
        passive_deletes=True,
    )

    # Card metadata:
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())
    qr_code_message = Column(String)

    # Apple Developer details:
    apple_pass_type_identifier = Column(String)
    apple_organization_name = Column(String)
    apple_team_identifier = Column(String)

    # Display related attributes:
    logo_text = Column(String, default="LV Membership")

    member_since = Column(DateTime)
    member_until = Column(DateTime)

    passfile_files = {
        "icon.png": "LV_Tee_Crest_onVerde_rgb_filled_icon.png",
        "icon@2x.png": "LV_Tee_Crest_onVerde_rgb_filled_icon@2x.png",
        "logo.png": "LosVerdes_Logo_RGB_72_Horizontal_BlackOnTransparent_CityYear_logo.png",
        "logo@2x.png": "LosVerdes_Logo_RGB_300_Horizontal_BlackOnTransparent_CityYear_logo@2x.png",
    }

    @property
    def apple_pass_serial_number(self):
        return str(getattr(self.serial_number, 'int'))

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
        )
        logger.debug(f"{passfile_attrs=}")
        for attr_name, attr_value in passfile_attrs.items():
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
        # breakpoint()
        logger.debug(f"{passfile.json_dict()=}")
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
