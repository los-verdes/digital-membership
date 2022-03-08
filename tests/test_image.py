from typing import TYPE_CHECKING

from member_card import image

if TYPE_CHECKING:
    from PIL import Image


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
