from typing import TYPE_CHECKING

import pytest
from member_card.passes import gpay

if TYPE_CHECKING:
    from flask import Flask
    from pytest_mock.plugin import MockerFixture


@pytest.fixture()
def google_pay_jwt(app: "Flask", mocker: "MockerFixture") -> gpay.GooglePassJwt:
    mock_crypt = mocker.patch("member_card.passes.gpay.crypt_google")
    with app.app_context():
        p = gpay.new_google_pass_jwt()
    mock_crypt.RSASigner.from_service_account_file.assert_called_once()
    return p


class TestGooglePassJwt:
    def test_init(self, google_pay_jwt: gpay.GooglePassJwt):
        assert google_pay_jwt

    def test_add_loyalty_class(self, google_pay_jwt: gpay.GooglePassJwt):
        test_loyalty_class = dict(loyalty_class="testing")
        google_pay_jwt.add_loyalty_class(test_loyalty_class)
        assert test_loyalty_class in google_pay_jwt.payload["loyaltyClasses"]

    def test_add_loyalty_object(self, google_pay_jwt: gpay.GooglePassJwt):
        test_loyalty_object = dict(loyalty_object="testing")
        google_pay_jwt.add_loyalty_object(test_loyalty_object)
        assert test_loyalty_object in google_pay_jwt.payload["loyaltyObjects"]

    def test_generate_unsigned_jwt(self, google_pay_jwt: gpay.GooglePassJwt):
        assert isinstance(google_pay_jwt.generate_unsigned_jwt(), dict)

    def test_generate_signed_jwt(
        self, google_pay_jwt: gpay.GooglePassJwt, mocker: "MockerFixture"
    ):
        mock_jwt_google = mocker.patch("member_card.passes.gpay.jwt_google")

        signed_jwt = google_pay_jwt.generate_signed_jwt()

        mock_jwt_google.encode.assert_called_once()
        assert signed_jwt == mock_jwt_google.encode.return_value
