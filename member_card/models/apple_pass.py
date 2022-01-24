from os.path import abspath, dirname, join

from logzero import logger
from member_card.db import Model
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from wallet.models import Barcode, BarcodeFormat, Generic, Pass

# from sqlalchemy.ext.declarative import declarative_base

# Base = declarative_base()
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


class ApplePass(Model):
    __tablename__ = "apple_pass"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="apple_passes")
    # annual_memberships = relationship(
    #     "AnnualMembership", secondary=apple_pass_to_membership_assoc_table
    # )

    # Apple Developer details:
    apple_pass_type_identifier = Column(String)
    apple_organization_name = Column(String)
    apple_team_identifier = Column(String)

    # Display related attributes:
    logo_text = Column(String, default="LV Membership")
    background_color = Column(String(8), default="#00B140")
    foreground_color = Column(String(8), default="#000000")

    passfile_files = {
        "icon.png": "LV_Tee_Crest_onVerde_rgb_filled_icon.png",
        "icon@2x.png": "LV_Tee_Crest_onVerde_rgb_filled_icon@2x.png",
        "logo.png": "LosVerdes_Logo_RGB_72_Horizontal_BlackOnTransparent_CityYear_logo.png",
        "logo@2x.png": "LosVerdes_Logo_RGB_300_Horizontal_BlackOnTransparent_CityYear_logo@2x.png",
    }

    @property
    def qr_code_message(self):
        return "Barcode message"

    @property
    def pass_info(self):

        pass_info = Generic()
        pass_info.addPrimaryField("name", self.user, "Member Name")
        pass_info.addSecondaryField(
            "member_since", self.user.member_since.strftime("%b %Y"), "Member Since"
        )
        pass_info.addBackField(
            "member_expiry_back",
            self.user.membership_expiry.strftime("%b %d, %Y"),
            "Good through",
        )

        # pass_info.addSecondaryField(
        #     "member_expiry", member_expiry_dt.strftime("%b %d, %Y"), "Good through"
        # )
        # pass_info.addPrimaryField("member_expiry", member_expiry_dt.strftime("%b %Y"), "Good through")

        # pass_info.addHeaderField(key="test_header", value="Testing the header", label="Test Header")
        # pass_info.addHeaderField(key="test_aux", value="Testing the aux", label="Test Aux")
        # pass_info.addBackField("hmm", "Hi there", "Hullo")
        # pass_info.addBackField(key="test_back", value="Testing the back", label="Test Back")
        return pass_info

    @property
    def passfile(self):
        passfile = Pass(
            passInformation=self.pass_info,
            passTypeIdentifier=self.apple_pass_type_identifier,
            organizationName=self.apple_organization_name,
            teamIdentifier=self.apple_team_identifier,
        )
        qr_code = Barcode(format=BarcodeFormat.QR, message=self.qr_code_message)

        passfile_attrs = dict(
            serialNumber=self.id,
            backgroundColor="rgb(0, 177, 64)",
            foregroundColor="rgb(0, 0, 0)",
            logoText=self.logo_text,
            barcode=qr_code,
        )
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
                passfile.addFile(passfile_filename, open(file_path, "rb"))

        return passfile

    def create_pkpass(self, key_filepath, key_password, pkpass_out_path=None):
        serial_number = self.id
        cert_filepath = get_certificate_path("certificate.pem")
        wwdr_cert_filepath = get_certificate_path("wwdr.pem")
        logger.debug(f"{cert_filepath=}")
        logger.debug(
            f"Creating passfile with {self.pass_type_identifier=} {serial_number=} (Signing details: {cert_filepath=} {key_filepath=} {wwdr_cert_filepath=}"
        )
        pkpass_string_buffer = self.passfile.create(
            certificate=cert_filepath,
            key=key_filepath,
            wwdr_certificate=wwdr_cert_filepath,
            password=key_password,
            zip_file=pkpass_out_path,  # os.path.join(secrets_dir, "test.pkpass"),
        )
        if pkpass_out_path:
            return pkpass_out_path
        return pkpass_string_buffer
