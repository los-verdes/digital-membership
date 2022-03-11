from member_card import passes
from urllib.parse import urlparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask
    from member_card.models import MembershipCard
    from pytest_mock.plugin import MockerFixture


class TestMemberCardPass:
    def test_logo_uri(self, app: "Flask"):
        p = passes.MemberCardPass()
        with app.app_context():
            assert urlparse(p.logo_uri)


class TestGooglePayPassClass:
    def test_hero_image_uri(self, app: "Flask"):
        p = passes.GooglePayPassClass(class_id="test-class-id")
        with app.app_context():
            assert urlparse(p.hero_image_uri)

    def test_to_dict(self, app: "Flask"):
        p = passes.GooglePayPassClass(class_id="test-class-id")
        with app.app_context():
            assert isinstance(p.to_dict(), dict)


class TestGooglePayPassObject:
    def test_to_dict(self, app: "Flask", fake_card: "MembershipCard"):
        p = passes.GooglePayPassObject(
            class_id="test-class-id", membership_card=fake_card
        )
        with app.app_context():
            assert isinstance(p.to_dict(), dict)


class TestPkPass:
    def test_create_passfile(self, app: "Flask", fake_card: "MembershipCard"):
        passfile = passes.create_passfile(membership_card=fake_card)
        assert passfile

    def test_create_pkpass(
        self, app: "Flask", fake_card: "MembershipCard", mocker: "MockerFixture"
    ):
        mock_create_passfile = mocker.patch("member_card.passes.create_passfile")
        key_filepath = "test-key_filepath"
        key_password = "test-key_password"
        pkpass_buffer = passes.create_pkpass(
            membership_card=fake_card,
            key_filepath=key_filepath,
            key_password=key_password,
        )
        assert pkpass_buffer
        mock_create_passfile().create.assert_called_once()

    def test_get_apple_pass_from_card(
        self, app: "Flask", fake_card: "MembershipCard", mocker: "MockerFixture"
    ):
        mock_create_pkpass = mocker.patch("member_card.passes.create_pkpass")
        passes.get_apple_pass_from_card(membership_card=fake_card)
        mock_create_pkpass.assert_called_once()

    def test_generate_and_upload_apple_pass(
        self, app: "Flask", fake_card: "MembershipCard", mocker: "MockerFixture"
    ):
        mock_get_pass = mocker.patch("member_card.passes.get_apple_pass_from_card")
        mock_upload = mocker.patch("member_card.passes.upload_file_to_gcs")

        mock_blob = mock_upload.return_value
        test_bucket_id = "this-os-a-test-bucket"
        mock_blob.bucket.id = test_bucket_id

        card_image_url = passes.generate_and_upload_apple_pass(
            membership_card=fake_card,
        )

        expected_url = f"{test_bucket_id}/membership-cards/apple-passes/{fake_card.apple_pass_serial_number}.pkpass"
        assert card_image_url == expected_url

        mock_get_pass.assert_called_once()
        mock_upload.assert_called_once()
