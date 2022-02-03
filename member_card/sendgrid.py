import json
import logging
import os
from datetime import datetime
from tempfile import TemporaryDirectory

from flask import g, render_template
from flask_login import login_user
from html2image import Html2Image
from PIL import Image, ImageChops

from member_card import utils
from member_card.models import User
from member_card.passes import get_or_create_membership_card
from member_card.storage import get_client, upload_file_to_gcs  # , get_presigned_url
from sendgrid import Asm, SendGridAPIClient
from sendgrid.helpers.mail import Mail

# from base64 import b64encode as b64e
# from textwrap import dedent
logger = logging.getLogger(__name__)


def generate_and_send_email(app, user, email, base_url):
    gcs_client = get_client()
    bucket = gcs_client.get_bucket(app.config["GCS_BUCKET_ID"])

    # attachment_ttl = timedelta(minutes=15)
    # attachment_ttl = timedelta(days=1)

    if not user.has_active_memberships:
        raise NotImplementedError

    img_aspect_ratio = 1.586
    img_height = 500
    img_width = int(img_height * img_aspect_ratio)
    membership_card = get_or_create_membership_card(
        user=user,
        base_url=base_url,
    )
    with app.test_request_context("/"):

        login_user(user=user)
        g.user = user
        html_content = render_template(
            "card_image.html.j2",
            membership_card=membership_card,
            card_height=img_height,
            card_width=img_width,
        )

    # with open("tmp_card_image.html", "w") as fp:
    #     fp.write(html_content)
    # compressed_img_height = 100
    # compressed_img_width = int(compressed_img_height * img_aspect_ratio)
    card_image_filename = f"{membership_card.serial_number.hex}.png"

    def trim(im):
        bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
        diff = ImageChops.difference(im, bg)
        diff = ImageChops.add(diff, diff, 2.0, -100)
        bbox = diff.getbbox()
        if bbox:
            return im.crop(bbox)
        return im

    with TemporaryDirectory() as td:
        output_path = td
        output_path = "/Users/jeffwecan/workspace/los-verdes/digital-membership"
        hti = Html2Image(
            output_path=output_path,
            temp_path=td,
            size=(img_width, img_height),
            custom_flags=[
                "--no-sandbox",
            ],
        )
        hti.screenshot(
            html_str=html_content,
            save_as=card_image_filename,
            # css_str=css_str,
        )
        image_path = os.path.join(output_path, card_image_filename)

        # compressed_image_path = image_path.replace(".png", "_compressed.png")
        img = Image.open(image_path)
        # img = img.convert("RGBA")
        img = trim(img)
        # img = img.resize(size=(compressed_img_width, compressed_img_height))
        img.save(image_path)  # , transparency=0) #, compress_level=9)
        # with open(compressed_image_path, mode="rb") as f:
        #     image_bytes = f.read()
        #     membership_card_png_b64 = b64e(image_bytes).decode()
        print(image_path)
        # breakpoint()
        remote_card_image_path = f"membership-cards/images/{card_image_filename}"
        blob = upload_file_to_gcs(
            bucket=bucket,
            local_file=image_path,
            remote_path=remote_card_image_path,
        )
        logger.debug(f"{blob=}")
        card_image_url = f"{app.config['GCS_BUCKET_ID']}/{remote_card_image_path}"
        # signed_url = get_presigned_url(blob, attachment_ttl)
    from member_card.passes import get_apple_pass_for_user

    with app.test_request_context("/"):
        local_apple_pass_path = get_apple_pass_for_user(user=user)
    remote_apple_pass_path = f"membership-cards/apple-passes/{membership_card.apple_pass_serial_number}.pkpass"
    apple_pass_blob = upload_file_to_gcs(
        bucket=bucket,
        local_file=local_apple_pass_path,
        remote_path=remote_apple_pass_path,
        content_type="application/vnd.apple.pkpass",
    )
    logger.debug(f"{apple_pass_blob=}")
    apple_pass_url = f"{app.config['GCS_BUCKET_ID']}/{remote_apple_pass_path}"
    # apple_pass_signed_url = get_presigned_url(apple_pass_blob, attachment_ttl)
    generated_on = datetime.utcnow().isoformat()
    # subject = f"{app.config['EMAIL_SUBJECT_TEXT']} (generated on: {generated_on})"
    subject = app.config["EMAIL_SUBJECT_TEXT"]
    serial_number = str(membership_card.serial_number)
    show_pass_signature = utils.sign(serial_number)
    template_data = {
        "subject": subject,
        "showPassSignature": show_pass_signature,
        # "applePassLink": "coming soon!",
        "membershipHistory": sorted(
            [m.to_dict() for m in user.annual_memberships],
            key=lambda x: x["created_on"],
        ),
        "card": dict(
            title="Los Verdes Membership Card",
            primary_info_text=membership_card.user.fullname,
            secondary_info_text=f"Member Since {membership_card.member_since.strftime('%b %Y')}",
            serial_number=membership_card.serial_number.hex,
            aux_info_text=f"Good through {membership_card.member_until.strftime('%b %d, %Y')}",
            # qr_code_b64_png=membership_card.qr_code_b64_png,
            qr_code_ascii=membership_card.qr_code_ascii,
        ),
        # "membershipCardBase64Png": membership_card_png_b64,
        # "applePassSignedUrl": apple_pass_signed_url,
        "cardImageUrl": card_image_url,
        "applePassUrl": apple_pass_url,
        "generated_on": generated_on,
        "generating_ip_address": False,  # TODO: propagate this information over here somehow...
    }

    # TODO: tmp testing dump here...
    # with open("sendgrid_template_data.json", "w") as fp:
    #     json.dump(template_data, fp, sort_keys=True, indent=4)

    sg = SendGridAPIClient(app.config["SENDGRID_API_KEY"])
    message = Mail(
        from_email=app.config["EMAIL_FROM_ADDRESS"],
        to_emails=user.email,
    )
    message.dynamic_template_data = template_data
    message.template_id = app.config["SENDGRID_TEMPLATE_ID"]
    group_id = 29631  # TODO: move this to a lookup or constant elsewhere
    message.asm = Asm(group_id)
    logger.info(
        f"sending '{subject}' email to: {user.email}",
        extra=dict(
            subject=subject, to_email=user.email, template_id=message.template_id
        ),
    )
    try:
        message_json = json.dumps(message.get(), sort_keys=True, indent=4)
        logger.debug(f"Outgoing email message {message_json=}")
        response = sg.send(message)
        logger.debug(f"SendGrid response: {response=}")

    except Exception as e:
        print(e.message)
        breakpoint()
        print(e.message)
