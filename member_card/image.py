import logging
import os
from tempfile import TemporaryDirectory

from flask import current_app
from html2image import Html2Image
from PIL import Image, ImageChops

from member_card.gcp import upload_file_to_gcs, get_bucket
from member_card.utils import get_jinja_template

logger = logging.getLogger(__name__)


def remove_image_background(img):
    img = img.convert("RGBA")

    img_data = img.getdata()

    updated_img_data = []

    for pixel in img_data:
        if pixel[0] == 255 and pixel[1] == 255 and pixel[2] == 255:
            updated_img_data.append((255, 255, 255, 0))
        else:
            updated_img_data.append(pixel)

    img.putdata(updated_img_data)
    return img


def trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im


def get_remote_card_image_url(membership_card):
    card_image_filename = f"{membership_card.serial_number.hex}.png"
    remote_card_image_path = f"membership-cards/images/{card_image_filename}"
    card_image_url = f"{get_bucket().id}/{remote_card_image_path}"
    return card_image_url


def ensure_uploaded_card_image(membership_card):
    card_image_filename = f"{membership_card.serial_number.hex}.png"
    remote_card_image_path = f"membership-cards/images/{card_image_filename}"

    image_bucket = get_bucket()
    card_image_url = f"{image_bucket.id}/{remote_card_image_path}"
    blob = image_bucket.blob(remote_card_image_path)
    if blob.exists():
        logger.info(
            f"{card_image_filename=} already present / previously uploaded for {membership_card=}: {card_image_url=} ({blob=})"
        )
    else:
        generate_and_upload_card_image(
            membership_card=membership_card,
            card_image_filename=card_image_filename,
            remote_card_image_path=remote_card_image_path,
        )

    return card_image_url


def generate_and_upload_card_image(
    membership_card, card_image_filename, remote_card_image_path
):
    with TemporaryDirectory() as image_output_path:
        image_path = generate_card_image(
            membership_card=membership_card,
            output_path=image_output_path,
            card_image_filename=card_image_filename,
        )

        blob = upload_file_to_gcs(
            local_file=image_path,
            remote_path=remote_card_image_path,
        )
        logger.info(
            f"{card_image_filename=} uploaded for {membership_card=}: ({blob=})"
        )
    return blob


def generate_card_image(membership_card, output_path, card_image_filename):
    img_aspect_ratio = 1.586
    img_height = 500
    img_width = int(img_height * img_aspect_ratio)
    image_template = get_jinja_template("card_image.html.j2")
    html_content = image_template.render(
        membership_card=membership_card,
        card_height=img_height,
        card_width=img_width,
        static_base_url=current_app.config["STATIC_ASSET_BASE_URL"],
    )

    screenshot_filename = f"screenshot_{card_image_filename}"

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
            save_as=screenshot_filename,
        )
        screenshot_path = os.path.join(output_path, screenshot_filename)
        img = Image.open(screenshot_path)
        img = remove_image_background(img)
        image_path = os.path.join(output_path, card_image_filename)
        img = trim(img)
        img.save(image_path)
    return image_path
