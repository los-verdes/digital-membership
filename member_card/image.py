import logging
import os
from tempfile import TemporaryDirectory

from html2image import Html2Image
from PIL import Image, ImageChops
from member_card.storage import upload_file_to_gcs
from member_card.utils import get_jinja_template

logger = logging.getLogger(__name__)


def trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im


def generate_and_upload_card_image(membership_card, bucket):
    with TemporaryDirectory() as image_output_path:
        image_path = generate_card_image(
            membership_card=membership_card,
            output_path=image_output_path,
        )

        card_image_filename = os.path.basename(image_path)
        remote_card_image_path = f"membership-cards/images/{card_image_filename}"
        card_image_url = f"{bucket.id}/{remote_card_image_path}"

        blob = upload_file_to_gcs(
            bucket=bucket,
            local_file=image_path,
            remote_path=remote_card_image_path,
        )
        logger.info(
            f"{card_image_filename=} uploaded for {membership_card=}: {card_image_url=} ({blob=})"
        )
    return card_image_url


def generate_card_image(membership_card, output_path):
    img_aspect_ratio = 1.586
    img_height = 500
    img_width = int(img_height * img_aspect_ratio)
    image_template = get_jinja_template("card_image.html.j2")
    html_content = image_template.render(
        membership_card=membership_card,
        card_height=img_height,
        card_width=img_width,
    )
    card_image_filename = f"{membership_card.serial_number.hex}.png"

    with TemporaryDirectory() as td:
        hti = Html2Image(
            output_path=output_path,
            temp_path=td,
            size=(img_width, img_height),
            custom_flags=[
                "--no-sandbox",
                "--hide-scrollbars",
            ],
        )
        hti.screenshot(
            html_str=html_content,
            save_as=card_image_filename,
        )
        image_path = os.path.join(output_path, card_image_filename)
        img = Image.open(image_path)
        img = trim(img)
        img.save(image_path)
    return image_path
