from typing import TYPE_CHECKING

import pytest
from member_card.passes import gpay

if TYPE_CHECKING:
    from flask import Flask
    from member_card.models import MembershipCard
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


@pytest.fixture()
def pay_client_mock(app: "Flask", mocker: "MockerFixture") -> gpay.GooglePayApiClient:
    mock_service_account = mocker.patch("member_card.passes.gpay.service_account")
    mock_auth_session = mocker.patch("member_card.passes.gpay.AuthorizedSession")
    with app.app_context():
        client = gpay.new_client()
    mock_service_account.Credentials.from_service_account_file.assert_called_once()
    return dict(
        client=client,
        mock_service_account=mock_service_account,
        mock_auth_session=mock_auth_session,
    )


class TestGooglePayApiClient:
    def test_init(self, pay_client_mock: gpay.GooglePayApiClient):
        assert pay_client_mock["client"]

    def test_request(self, pay_client_mock: gpay.GooglePayApiClient):
        response = pay_client_mock["client"].request(
            method="GET",
            resource_type="test-resource_type",
            resource_id="test-resource_id",
        )
        assert response

    def test_request_with_json_payload(self, pay_client_mock: gpay.GooglePayApiClient):
        response = pay_client_mock["client"].request(
            method="GET",
            resource_type="test-resource_type",
            resource_id="test-resource_id",
            json_payload=dict(type="test"),
        )
        assert response

    def test_get_pass_class(self, pay_client_mock: gpay.GooglePayApiClient):
        response = pay_client_mock["client"].get_pass_class(
            class_id="test-class_id",
        )
        assert response

    def test_get_pass_object(self, pay_client_mock: gpay.GooglePayApiClient):
        response = pay_client_mock["client"].get_pass_object(
            object_id="test-object_id",
        )
        assert response

    def test_insert_class(self, pay_client_mock: gpay.GooglePayApiClient):
        response = pay_client_mock["client"].insert_class(
            class_id="test-class_id",
            payload=dict(),
        )
        assert response

    def test_insert_object(self, pay_client_mock: gpay.GooglePayApiClient):
        response = pay_client_mock["client"].insert_object(
            object_id="test-object_id",
            payload=dict(),
        )
        assert response

    def test_patch_class(self, pay_client_mock: gpay.GooglePayApiClient):
        response = pay_client_mock["client"].patch_class(
            class_id="test-class_id",
            payload=dict(),
        )
        assert response

    def test_modify_pass_class_patch(self, app: "Flask", mocker: "MockerFixture"):
        mock_new_client = mocker.patch("member_card.passes.gpay.new_client")
        with app.app_context():
            response = gpay.modify_pass_class(operation="patch")
        assert response
        mock_new_client.return_value.patch_class.assert_called_once()

    def test_modify_pass_class_insert(self, app: "Flask", mocker: "MockerFixture"):
        mock_new_client = mocker.patch("member_card.passes.gpay.new_client")
        with app.app_context():
            response = gpay.modify_pass_class(operation="insert")
        assert response
        mock_new_client.return_value.insert_class.assert_called_once()

    # def test_patch_object(self, pay_client_mock: gpay.GooglePayApiClient):
    #     response = pay_client_mock["client"].patch_object(
    #         object_id="test-object_id",
    #         payload=dict(),
    #     )
    #     assert response


class TestGeneratePassJwt:
    def test_generate_pass_jwt(
        self, app: "Flask", fake_card: "MembershipCard", mocker: "MockerFixture"
    ):
        mock_new_google_pass_jwt = mocker.patch(
            "member_card.passes.gpay.new_google_pass_jwt"
        )
        mock_new_client = mocker.patch("member_card.passes.gpay.new_client")
        mock_gpay_client = mock_new_client.return_value

        with app.app_context():
            result = gpay.generate_pass_jwt(membership_card=fake_card)

        assert result

        mock_new_google_pass_jwt.assert_called_once()
        mock_gpay_client.insert_object.assert_called_once()
