from typing import TYPE_CHECKING

from member_card import utils

if TYPE_CHECKING:
    from flask import Flask
    from member_card.models import MembershipCard

from flask.testing import FlaskClient


class TestPasskit:
    def test_register_device_no_auth_token(
        self, app: "Flask", client: "FlaskClient", fake_card: "MembershipCard"
    ):
        test_device_id = "test-device_library_identifier"
        test_pass_type_id = app.config["APPLE_DEVELOPER_PASS_TYPE_ID"]
        response = client.post(
            f"/passkit/v1/devices/{test_device_id}/registrations/{test_pass_type_id}/{fake_card.apple_pass_serial_number}"
        )
        assert response.status_code == 401

    def test_register_device_unsupported_auth_type(
        self, app: "Flask", client: "FlaskClient", fake_card: "MembershipCard"
    ):
        test_auth_header = (
            f"UnsupportedPass {utils.sign(fake_card.authentication_token_hex)}"
        )
        test_device_id = "test-device_library_identifier"
        test_pass_type_id = app.config["APPLE_DEVELOPER_PASS_TYPE_ID"]
        response = client.post(
            f"/passkit/v1/devices/{test_device_id}/registrations/{test_pass_type_id}/{fake_card.apple_pass_serial_number}",
            headers=dict(Authorization=test_auth_header),
        )
        assert response.status_code == 401

    def test_register_device_invalid_auth_token(
        self, app: "Flask", client: "FlaskClient", fake_card: "MembershipCard"
    ):
        test_auth_header = "ApplePass a-bunk-token"
        test_device_id = "test-device_library_identifier"
        test_pass_type_id = app.config["APPLE_DEVELOPER_PASS_TYPE_ID"]
        response = client.post(
            f"/passkit/v1/devices/{test_device_id}/registrations/{test_pass_type_id}/{fake_card.apple_pass_serial_number}",
            headers=dict(Authorization=test_auth_header),
        )
        assert response.status_code == 401

    def test_register_device_unexpected_pass_type_id(
        self, app: "Flask", client: "FlaskClient", fake_card: "MembershipCard"
    ):
        test_auth_header = f"ApplePass {utils.sign(fake_card.authentication_token_hex)}"
        test_device_id = "test-device_library_identifier"
        test_pass_type_id = "test-pass_type_identifier"
        response = client.post(
            f"/passkit/v1/devices/{test_device_id}/registrations/{test_pass_type_id}/{fake_card.apple_pass_serial_number}",
            headers=dict(Authorization=test_auth_header),
        )
        assert response.status_code == 401

    def test_register_device_no_push_token_provided(
        self, app: "Flask", client: "FlaskClient", fake_card: "MembershipCard"
    ):
        test_auth_header = f"ApplePass {utils.sign(fake_card.authentication_token_hex)}"
        test_device_id = "test-device_library_identifier"
        test_pass_type_id = app.config["APPLE_DEVELOPER_PASS_TYPE_ID"]
        response = client.post(
            f"/passkit/v1/devices/{test_device_id}/registrations/{test_pass_type_id}/{fake_card.apple_pass_serial_number}",
            headers=dict(Authorization=test_auth_header),
        )
        assert response.status_code == 422

    def test_register_device_push_token_provided(
        self, app: "Flask", client: "FlaskClient", fake_card: "MembershipCard"
    ):
        test_auth_header = f"ApplePass {utils.sign(fake_card.authentication_token_hex)}"
        test_device_id = "test-device_library_identifier"
        test_pass_type_id = app.config["APPLE_DEVELOPER_PASS_TYPE_ID"]
        test_push_token = "test_push_token"
        response = client.post(
            f"/passkit/v1/devices/{test_device_id}/registrations/{test_pass_type_id}/{fake_card.apple_pass_serial_number}",
            headers=dict(Authorization=test_auth_header),
            json=dict(pushToken=test_push_token),
        )
        assert response.status_code == 201

        already_registered_device_resp = client.post(
            f"/passkit/v1/devices/{test_device_id}/registrations/{test_pass_type_id}/{fake_card.apple_pass_serial_number}",
            headers=dict(Authorization=test_auth_header),
            json=dict(pushToken=test_push_token),
        )
        assert already_registered_device_resp.status_code == 200
