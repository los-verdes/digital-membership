import logging
from typing import TYPE_CHECKING

import pytest
from google.cloud.storage.blob import Blob

from member_card import image

if TYPE_CHECKING:
    from PIL import Image
    from pytest_mock.plugin import MockerFixture

    from member_card.models import MembershipCard


def test_remove_image_background(untrimmed_with_bg_img: "Image"):
    untrimmed_img = image.remove_image_background(untrimmed_with_bg_img)

    # We expect img dimensions to be unchanged here:
    assert untrimmed_img.width == untrimmed_with_bg_img.width
    assert untrimmed_img.height == untrimmed_with_bg_img.height

    # However, the background color should have been made transparent! :D
    transparent_white_pixel = (255, 255, 255, 0)
    img_data = untrimmed_img.getdata()
    top_left_pixel = img_data[0]
    assert top_left_pixel == transparent_white_pixel
    bottom_right_pixel = img_data[-1]
    assert bottom_right_pixel == transparent_white_pixel


def test_trim_without_image_background(untrimmed_img: "Image"):
    trimmed_img = image.trim(untrimmed_img)
    trimmed_img.save("trimmed.png")

    # After triming, the resulting image should have smaller dimensions:
    assert trimmed_img.width < untrimmed_img.width
    assert trimmed_img.height < untrimmed_img.height

    # Also, the top-left & bottom-right pixels should be an opaque color
    # (as the center of our test image is a bright verde colored square! :D)
    bright_verde_pixel = (0, 177, 64, 255)
    img_data = trimmed_img.getdata()
    top_left_pixel = img_data[0]
    assert top_left_pixel == bright_verde_pixel
    bottom_right_pixel = img_data[-1]
    assert bottom_right_pixel == bright_verde_pixel


def test_trim_with_image_background(untrimmed_with_bg_img: "Image"):
    trimmed_img = image.trim(untrimmed_with_bg_img)
    trimmed_img.save("trimmed.png")

    # With a background, triming is a no-go. Thus the resulting image should
    # have the dimensions as the original:
    assert trimmed_img.width == untrimmed_with_bg_img.width
    assert trimmed_img.height == untrimmed_with_bg_img.height


@pytest.fixture()
def mock_uploaded_blob(
    mocker: "MockerFixture",
):
    test_bucket_id = "this-os-a-test-bucket"

    mock_blob = mocker.create_autospec(Blob)
    mock_blob.exists.return_value = False

    mock_get_bucket = mocker.patch("member_card.image.get_bucket")
    mock_bucket = mock_get_bucket.return_value
    mock_bucket.id = test_bucket_id
    mock_bucket.blob.return_value = mock_blob

    mock_blob.bucket = mock_bucket

    def mock_upload_side_effect(*args, **kwargs):
        logging.debug(f"mock_upload_side_effect(): {args=} {kwargs=}")
        mock_blob.exists.return_value = True
        return mock_blob

    mock_blob.upload_from_filename.side_effect = mock_upload_side_effect

    yield mock_blob


@pytest.fixture()
def mock_image(
    mocker: "MockerFixture",
):
    mock_image = mocker.patch("member_card.image.Image")
    # since these Image instances have a bunch of chained calls...:
    chained_image_methods = ["open", "convert", "crop"]
    for chained_image_method in chained_image_methods:
        getattr(mock_image, chained_image_method).return_value = mock_image
    return mock_image


def test_generate_and_upload_card_image(
    fake_card: "MembershipCard", mocker: "MockerFixture", mock_uploaded_blob, mock_image
):
    mock_html2image = mocker.patch("member_card.image.Html2Image")
    mock_hti = mock_html2image.return_value
    return_value = image.generate_and_upload_card_image(
        image_bucket=mock_uploaded_blob.bucket,
        membership_card=fake_card,
    )

    assert return_value == mock_uploaded_blob
    mock_hti.screenshot.assert_called_once()
    mock_image.save.assert_called_once()


def test_ensure_uploaded_card_image_no_extant_blob(
    fake_card: "MembershipCard", mocker: "MockerFixture", mock_uploaded_blob
):
    mock_upload = mocker.patch("member_card.image.generate_and_upload_card_image")
    test_bucket_id = mock_uploaded_blob.bucket.id
    card_image_url = image.ensure_uploaded_card_image(
        membership_card=fake_card,
    )

    expected_url = (
        f"{test_bucket_id}/membership-cards/images/{fake_card.serial_number.hex}.png"
    )
    assert card_image_url == expected_url
    mock_upload.assert_called()


def test_ensure_uploaded_card_image_extant_blob(
    fake_card: "MembershipCard", mocker: "MockerFixture", mock_uploaded_blob
):
    test_bucket_id = mock_uploaded_blob.bucket.id
    mock_uploaded_blob.exists.return_value = True
    mock_upload = mocker.patch("member_card.image.generate_and_upload_card_image")
    card_image_url = image.ensure_uploaded_card_image(
        membership_card=fake_card,
    )

    expected_url = (
        f"{test_bucket_id}/membership-cards/images/{fake_card.serial_number.hex}.png"
    )
    assert card_image_url == expected_url
    mock_upload.assert_not_called()
