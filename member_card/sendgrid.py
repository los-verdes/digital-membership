import json
import logging
from datetime import datetime

import flask
from jinja2 import Environment, PackageLoader, select_autoescape

from sendgrid import Asm, SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)


def generate_email_message(
    membership_card,
    card_image_url,
    apple_pass_url,
    subject=None,
    submitted_on=None,
    submitting_ip_address=None,
):
    app = flask.current_app

    if subject is None:
        subject = app.config["EMAIL_SUBJECT_TEXT"]

    if submitted_on is None:
        submitted_on = datetime.utcnow().isoformat()

    message = Mail(
        from_email=app.config["EMAIL_FROM_ADDRESS"],
        to_emails=membership_card.user.email,
    )
    message.asm = Asm(int(app.config["SENDGRID_GROUP_ID"]))
    message.template_id = app.config["SENDGRID_TEMPLATE_ID"]
    message.dynamic_template_data = {
        "subject": subject,
        "card": dict(
            title="Los Verdes Membership Card",
            primary_info_text=membership_card.user.fullname,
            secondary_info_text=f"Member Since {membership_card.member_since.strftime('%b %Y')}",
            serial_number=membership_card.serial_number.hex,
            aux_info_text=f"Good through {membership_card.member_until.strftime('%b %d, %Y')}",
            qr_code_ascii=membership_card.qr_code_ascii,
        ),
        "cardImageUrl": card_image_url,
        "applePassUrl": apple_pass_url,
        "submitted_on": submitted_on,
        "submitting_ip_address": submitting_ip_address,  # TODO: propagate this information over here somehow...
        "googlePassUrl": membership_card.google_pass_save_url,
    }

    return message


def send_email_message(email_message):
    tos = [p.tos for p in email_message.personalizations]
    logger.info(
        f"sending email message to: {tos}",
        extra=dict(tos=tos, template_id=email_message.template_id),
    )
    sg = SendGridAPIClient(flask.current_app.config["SENDGRID_API_KEY"])
    message_json = json.dumps(email_message.get(), sort_keys=True, indent=4)
    logger.debug(f"Outgoing email message {message_json=}")
    response = sg.send(email_message)
    logger.debug(f"SendGrid response: {response=}")
    return response


def update_sendgrid_template():
    app = flask.current_app

    sg = SendGridAPIClient(app.config["SENDGRID_API_KEY"])
    template_id = app.config["SENDGRID_TEMPLATE_ID"]
    get_template_resp = sg.client.templates._(template_id).get()
    template = json.loads(get_template_resp.body.decode())
    version = template["versions"][0]
    version_id = version["id"]

    env = Environment(
        loader=PackageLoader(__name__),
        autoescape=select_autoescape(),
        variable_start_string="{~~ ",
        variable_end_string=" ~~}",
        comment_start_string="{#~",
        comment_end_string="~#}",
    )
    html_template = env.get_template("sendgrid/card_distribution_email.html.j2")
    updated_html_content = html_template.render(
        preview_text="Your requested Los Verdes membership card details are attached! PNG image, Apple Wallet and Google Play pass formats enclosed. =D",
        view_online_href="https://card.losverd.es",
        logo_src="cstatic.losverd.es/static/LosVerdes_Logo_RGB_300_Horizontal_VerdeOnTransparent_CityYear.png",
        downloads_img_src="cstatic.losverd.es/static/small_lv_hands.png",
        footer_logo_src="cstatic.losverd.es/static/lv_hands.png",
        card_img_src="{{cardImageUrl}}",
    )
    version["html_content"] = updated_html_content.strip()

    plain_template = env.get_template("sendgrid/card_distribution_email.txt")
    updated_plain_content = plain_template.render()
    version["plain_content"] = updated_plain_content.strip()

    # PATCH Response: 400 b'{"error":"You cannot switch editors once a dynamic template version has been created."}\n'
    del version["editor"]

    patch_version_resp = (
        sg.client.templates._(template_id)
        .versions._(version_id)
        .patch(request_body=version)
    )

    logger.debug(f"{patch_version_resp.status_code=}:: {patch_version_resp.headers=}")
    logger.info(f"{patch_version_resp.body}")

    return version
