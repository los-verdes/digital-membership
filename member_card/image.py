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


def ensure_uploaded_card_image(membership_card):
    image_bucket = get_bucket()
    blob = image_bucket.blob(membership_card.remote_image_path)
    if blob.exists():
        logger.info(
            f"{membership_card.remote_image_path} already present / previously uploaded for {membership_card=}: {blob=})"
        )
    else:
        generate_and_upload_card_image(
            image_bucket=image_bucket,
            membership_card=membership_card,
        )

    return f"{image_bucket.id}/{membership_card.remote_image_path}"


def generate_and_upload_card_image(image_bucket, membership_card):
    with TemporaryDirectory() as image_output_path:
        image_path = generate_card_image(
            membership_card=membership_card,
            output_path=image_output_path,
            card_image_filename=membership_card.image_filename,
        )

        blob = upload_file_to_gcs(
            bucket=image_bucket,
            local_file=image_path,
            remote_path=membership_card.remote_image_path,
        )
        logger.info(
            f"{membership_card.image_filename=} uploaded for {membership_card=}: ({blob=})"
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
