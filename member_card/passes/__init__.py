import logging
import tempfile
from os.path import join

import flask
from flask import current_app
from member_card.db import db
from member_card.passes.apple_wallet import tmp_apple_developer_key
from member_card.gcp import upload_file_to_gcs
from member_card.utils import sign
from wallet.models import Barcode, BarcodeFormat, Generic, Pass

logger = logging.getLogger(__name__)


class MemberCardPass(object):
    header = "Los Verdes Membership Card"

    logo = "google_pass_logo_2021.png"
    icon = "LV_Tee_Crest_onVerde_rgb_filled_icon@2x.png"
    description = "Los Verdes Membership Card"

    background_color = "rgb((0, 177, 64)"
    foreground_color = "rgb(0, 0, 0)"

    @property
    def logo_uri(self):
        return f"{current_app.config['STATIC_ASSET_BASE_URL']}/{self.logo}"


class AppleWalletPass(MemberCardPass):
    passfile_files = {
        "icon.png": "LV_Tee_Crest_onVerde_rgb_filled_icon.png",
        "icon@2x.png": "LV_Tee_Crest_onVerde_rgb_filled_icon@2x.png",
        "logo.png": "LosVerdes_Logo_RGB_72_Horizontal_BlackOnTransparent_CityYear_logo.png",
        "logo@2x.png": "LosVerdes_Logo_RGB_300_Horizontal_BlackOnTransparent_CityYear_logo@2x.png",
    }


class GooglePayPassClass(MemberCardPass):
    hero_image = "google_pass_hero_2021.png"

    def __init__(self, class_id):
        self.class_id = class_id

    @property
    def hero_image_uri(self):
        return f"{current_app.config['STATIC_ASSET_BASE_URL']}/{self.hero_image}"

    def to_dict(self):
        # below defines an Loyalty class. For more properties, check:
        # https://developers.google.com/pay/passes/reference/v1/loyaltyclass/insert
        # https://developers.google.com/pay/passes/guides/pass-verticals/loyalty/design

        payload = {
            # required fields
            "id": self.class_id,
            "issuerName": current_app.config["GOOGLE_PAY_ISSUER_NAME"],
            "programName": current_app.config["GOOGLE_PAY_PROGRAM_NAME"],
            "hexBackgroundColor": self.background_color,
            "multipleDevicesAndHoldersAllowedStatus": "ONE_USER_ALL_DEVICES",
            "accountNameLabel": "Member Name",
            "accountIdLabel": "Email Address",
            "reviewStatus": "underReview",
            "programLogo": {
                "kind": "walletobjects#image",
                "sourceUri": {
                    "kind": "walletobjects#uri",
                    "uri": self.logo_uri,
                },
            },
            "heroImage": {
                "kind": "walletobjects#image",
                "sourceUri": {
                    "kind": "walletobjects#uri",
                    "uri": self.hero_image_uri,
                },
            },
            "textModulesData": [
                {
                    "id": "listFirstRow",
                    "body": "Los Verdes",
                },
                {
                    "id": "listSecondRow",
                    "body": "Membership Card",
                },
            ],
            "linksModuleData": {
                "uris": [
                    {
                        "uri": "https://losverdesatx.org/",
                        "description": "Los Verdes - Main Website",
                        "id": "mainSite",
                    }
                ]
            },
            "homepageUri": {
                "uri": "https://card.losverd.es",
                "description": "Los Verdes - Membership Card Portal",
            },
            "classTemplateInfo": {
                "detailsTemplateOverride": {
                    "detailsItemInfos": [
                        {
                            "item": {
                                "firstValue": {
                                    "fields": [
                                        {
                                            "fieldPath": "object.textModulesData['serialNumber']",
                                        }
                                    ]
                                }
                            }
                        },
                        {
                            "item": {
                                "firstValue": {
                                    "fields": [
                                        {
                                            "fieldPath": "class.homepageUri",
                                        }
                                    ]
                                }
                            }
                        },
                        {
                            "item": {
                                "firstValue": {
                                    "fields": [
                                        {
                                            "fieldPath": "class.linksModuleData.uris['mainSite']"
                                        }
                                    ]
                                }
                            }
                        },
                    ]
                },
                "listTemplateOverride": {
                    "firstRowOption": {
                        "fieldOption": {
                            "fields": [
                                {"fieldPath": "class.textModulesData['listFirstRow']"}
                            ]
                        }
                    },
                    "secondRowOption": {
                        "fieldOption": {
                            "fields": [
                                {"fieldPath": "class.textModulesData['listSecondRow']"}
                            ]
                        }
                    },
                },
                "cardTemplateOverride": {
                    "cardRowTemplateInfos": [
                        {
                            "oneItem": {
                                "item": {
                                    "firstValue": {
                                        "fields": [
                                            {
                                                "fieldPath": "object.textModulesData['memberName']"
                                            }
                                        ]
                                    }
                                },
                            }
                        },
                        {
                            "twoItems": {
                                "startItem": {
                                    "firstValue": {
                                        "fields": [
                                            {
                                                "fieldPath": "object.textModulesData['memberSince']"
                                            }
                                        ]
                                    }
                                },
                                "endItem": {
                                    "firstValue": {
                                        "fields": [
                                            {
                                                "fieldPath": "object.textModulesData['goodUntil']"
                                            }
                                        ]
                                    }
                                },
                            }
                        },
                    ]
                },
            },
        }
        return payload


class GooglePayPassObject(object):
    def __init__(self, class_id, membership_card):
        self.class_id = class_id
        self.serial_number = str(membership_card.serial_number)
        issuer_id = current_app.config["GOOGLE_PAY_ISSUER_ID"]
        self.object_id = f"{issuer_id}.{self.serial_number}"

        self.account_name = membership_card.user.fullname
        self.account_id = membership_card.user.email

        self.barcode = {
            "type": "QR_CODE",
            "value": membership_card.qr_code_message,
            # "alternateText": self.serial_number,
        }

        self.valid_time_interval = {
            "start": dict(date=membership_card.google_pass_start_timestamp),
            "end": dict(date=membership_card.google_pass_expiry_timestamp),
        }
        # self.member_name = membership_card.user.fullname
        self.member_since = membership_card.user.member_since.strftime("%b %Y")
        self.good_until = membership_card.user.membership_expiry.strftime("%b %d, %Y")

        logger.debug(
            f"GooglePayPassObject initialized! ID: {self.object_id}",
            extra=self.__dict__,
        )

    def to_dict(self):
        # below defines an loyalty object. For more properties, check:
        # https://developers.google.com/pay/passes/reference/v1/loyaltyobject/insert
        # https://developers.google.com/pay/passes/guides/pass-verticals/loyalty/design

        payload = {
            # required fields
            "id": self.object_id,
            "classId": self.class_id,
            "state": "active",  # optional
            "accountName": self.account_name,
            "accountId": self.account_id,
            "barcode": self.barcode,
            "validTimeInterval": self.valid_time_interval,
            "messages": [],
            "textModulesData": [
                {
                    "header": "Member Name",
                    "id": "memberName",
                    "body": self.account_name,
                },
                {
                    "header": "Member Since",
                    "id": "memberSince",
                    "body": self.member_since,
                },
                {
                    "header": "Good Until",
                    "id": "goodUntil",
                    "body": self.good_until,
                },
                {
                    "header": "Serial Number",
                    "id": "serialNumber",
                    "body": self.serial_number,
                },
            ],
        }

        return payload


def create_passfile(membership_card):
    pass_info = Generic()
    pass_info.addPrimaryField("name", membership_card.user.fullname, "Member Name")
    pass_info.addSecondaryField(
        "member_since",
        membership_card.user.member_since.strftime("%b %Y"),
        "Member Since",
    )
    pass_info.addSecondaryField(
        "member_expiry_back",
        membership_card.user.membership_expiry.strftime("%b %d, %Y"),
        "Good through",
    )
    pass_info.addBackField(
        "serial_number",
        membership_card.serial_number_hex,
        "Card #",
    )
    pass_kwargs = dict(
        passInformation=pass_info,
        passTypeIdentifier=membership_card.apple_pass_type_identifier,
        organizationName=membership_card.apple_organization_name,
        teamIdentifier=membership_card.apple_team_identifier,
    )
    log_extra = pass_kwargs
    logger.debug(
        f"Generating Pass() for {membership_card.apple_pass_serial_number} ({str(membership_card.serial_number)})",
        extra=log_extra,
    )
    passfile = Pass(**pass_kwargs)

    qr_code = Barcode(format=BarcodeFormat.QR, message=membership_card.qr_code_message)

    passfile_attrs = dict(
        description=AppleWalletPass.description,
        serialNumber=membership_card.apple_pass_serial_number,
        backgroundColor=AppleWalletPass.background_color,
        foregroundColor=AppleWalletPass.foreground_color,
        logoText=membership_card.logo_text,
        barcode=qr_code,
        webServiceURL=membership_card.web_service_url,
        authenticationToken=sign(membership_card.authentication_token_hex),
        expirationDate=membership_card.apple_pass_expiry_timestamp,
        voided=membership_card.is_voided,
        userInfo=membership_card.user.to_dict(),
    )
    log_extra.update(dict(passfile_attrs=passfile_attrs))
    for attr_name, attr_value in passfile_attrs.items():
        setattr(
            passfile,
            attr_name,
            attr_value,
        )

    # Including the icon and logo is necessary for the passbook to be valid.
    static_dir = join(current_app.config["BASE_DIR"], "static")
    for passfile_filename, local_filename in AppleWalletPass.passfile_files.items():
        file_path = join(static_dir, local_filename)
        logger.debug(
            f"adding {file_path} as pass file: {passfile_filename}", extra=log_extra
        )
        passfile.addFile(passfile_filename, open(file_path, "rb"))

    logger.debug(
        f"Pass() for {membership_card.apple_pass_serial_number} ({str(membership_card.serial_number)}) successfully created!",
        extra=log_extra,
    )
    return passfile


def create_pkpass(membership_card, key_filepath, key_password, pkpass_out_path=None):
    serial_number = membership_card.id
    cert_dir = join(current_app.config["BASE_DIR"], "certificates")
    cert_filepath = join(cert_dir, "certificate.pem")
    wwdr_cert_filepath = join(cert_dir, "wwdr.pem")
    log_extra = dict(
        apple_serial_number=membership_card.apple_pass_serial_number,
        serial_number=membership_card.serial_number_hex,
        pass_type_identifier=membership_card.apple_pass_type_identifier,
        signing_cert_details=dict(
            cert_filepath=cert_filepath,
            key_filepath=key_filepath,
            wwdr_cert_filepath=wwdr_cert_filepath,
        ),
    )
    logger.debug(
        f"Creating passfile with {membership_card.apple_pass_type_identifier=} {serial_number=}",
        extra=log_extra,
    )
    passfile = create_passfile(membership_card)
    pkpass_string_buffer = passfile.create(
        certificate=cert_filepath,
        key=key_filepath,
        wwdr_certificate=wwdr_cert_filepath,
        password=key_password,
        zip_file=pkpass_out_path,
    )
    return pkpass_string_buffer


def get_apple_pass_from_card(membership_card):
    db.session.add(membership_card)
    db.session.commit()

    _, pkpass_out_path = tempfile.mkstemp()
    with tmp_apple_developer_key() as key_filepath:
        create_pkpass(
            membership_card=membership_card,
            key_filepath=key_filepath,
            key_password=flask.current_app.config["APPLE_PASS_PRIVATE_KEY_PASSWORD"],
            pkpass_out_path=pkpass_out_path,
        )
    return pkpass_out_path


def generate_and_upload_apple_pass(membership_card):
    local_apple_pass_path = get_apple_pass_from_card(membership_card)
    remote_apple_pass_path = f"membership-cards/apple-passes/{membership_card.apple_pass_serial_number}.pkpass"
    blob = upload_file_to_gcs(
        local_file=local_apple_pass_path,
        remote_path=remote_apple_pass_path,
        content_type="application/vnd.apple.pkpass",
    )
    apple_pass_url = f"{blob.bucket.id}/{remote_apple_pass_path}"
    logger.info(
        f"{local_apple_pass_path=} uploaded for {membership_card.apple_pass_serial_number} ({str(membership_card.serial_number)})",
        extra=dict(
            bucket=str(blob.bucket),
            local_apple_pass_path=local_apple_pass_path,
            remote_apple_pass_path=remote_apple_pass_path,
            apple_pass_url=apple_pass_url,
            blob=str(blob),
        ),
    )
    return apple_pass_url
