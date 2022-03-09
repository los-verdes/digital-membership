from typing import TYPE_CHECKING

from dateutil.parser import parse
from member_card.models import MembershipCard

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


def test_google_pay_jwt_cached_locally(mocker: "MockerFixture"):
    mock_gen_jwt = mocker.patch("member_card.models.membership_card.generate_pass_jwt")
    fake_card = MembershipCard()
    assert fake_card.google_pay_jwt
    assert fake_card.google_pay_jwt
    mock_gen_jwt.assert_called_once()


def test_google_pass_save_url(fake_card: "MembershipCard", mocker: "MockerFixture"):
    mocker.patch("member_card.models.membership_card.generate_pass_jwt")
    assert fake_card.google_pass_save_url.startswith(
        "https://pay.google.com/gp/v/save/"
    )


def test_is_voided(fake_card: "MembershipCard"):
    assert fake_card.is_voided is False


def test_google_pass_start_timestamp(fake_card: "MembershipCard"):
    assert parse(fake_card.google_pass_start_timestamp)


def test_google_pass_expiry_timestamp(fake_card: "MembershipCard"):
    assert parse(fake_card.google_pass_expiry_timestamp)


def test_apple_pass_expiry_timestamp(fake_card: "MembershipCard"):
    assert parse(fake_card.apple_pass_expiry_timestamp)


def test_apple_pass_serial_number(fake_card: "MembershipCard"):
    assert isinstance(fake_card.apple_pass_serial_number, str)


def test_serial_number_hex(fake_card: "MembershipCard"):
    assert isinstance(fake_card.serial_number_hex, str)


def test_qr_code_b64_png(fake_card: "MembershipCard"):
    assert isinstance(fake_card.qr_code_b64_png, str)


def test_qr_code_ascii(fake_card: "MembershipCard"):
    assert isinstance(fake_card.qr_code_ascii, str)


def test_authentication_token_hex(fake_card: "MembershipCard"):
    assert isinstance(fake_card.authentication_token_hex, str)
