import pytest
from typing import TYPE_CHECKING

from member_card import bigcommerce

if TYPE_CHECKING:
    from flask import Flask
    from member_card.models import MembershipCard
    from pytest_mock.plugin import MockerFixture
    from requests_mock.contrib.fixture import Fixture as RequestsMockFixture


def test_get_app_client_for_store(
    app: "Flask", fake_card: "MembershipCard", mocker: "MockerFixture"
):
    mock_bigcomm_api = mocker.patch("member_card.bigcommerce.BigcommerceApi")
    mock_store_hash = "mock_store_hash"
    app_client = bigcommerce.get_app_client_for_store(store_hash=mock_store_hash)
    assert app_client == mock_bigcomm_api.return_value


def test_get_bespoke_client_for_store(
    app: "Flask", fake_card: "MembershipCard", mocker: "MockerFixture"
):
    mock_bigcomm_api = mocker.patch("member_card.bigcommerce.BiggercommerceApi")
    app_client = bigcommerce.get_bespoke_client_for_store()
    assert app_client == mock_bigcomm_api.return_value


@pytest.fixture(scope="session")
def bigcomm_app_client() -> "Flask":
    mock_store_hash = "mock_store_hash"
    app_client = bigcommerce.BiggercommerceApi(
        client_id="BIGCOMMERCE_CLIENT_ID",
        store_hash=mock_store_hash,
        access_token="BIGCOMMERCE_ACCESS_TOKEN",
    )

    yield app_client


class TestBiggercommerceApi:
    def test_get_all_scripts(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        requests_mock.get(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/content/scripts"
        )
        return_value = bigcomm_app_client.get_all_scripts()
        assert return_value

    def test_create_a_script(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        requests_mock.post(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/content/scripts"
        )
        return_value = bigcomm_app_client.create_a_script(
            name="test",
            src_filename="test.js",
        )
        assert return_value

    def test_get_all_widgets(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        requests_mock.get(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/content/widgets"
        )
        return_value = bigcomm_app_client.get_all_widgets()
        assert return_value

    def test_get_all_placements(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        requests_mock.get(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/content/placements"
        )
        return_value = bigcomm_app_client.get_all_placements()
        assert return_value

    def test_create_a_placements(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        requests_mock.post(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/content/placements"
        )
        return_value = bigcomm_app_client.create_a_placement(
            widget_uuid="1234",
            template_file="template.html",
            region="yerarse",
        )
        assert return_value

    def test_update_a_placements(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        mock_placement_uuid = "1234"
        requests_mock.put(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/content/placements/{mock_placement_uuid}"
        )
        return_value = bigcomm_app_client.update_a_placement(
            placement_uuid=mock_placement_uuid,
            widget_uuid="1234",
            template_file="template.html",
            region="yerarse",
        )
        assert return_value

    def test_delete_a_placements(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        mock_placement_uuid = "1234"
        requests_mock.delete(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/content/placements/{mock_placement_uuid}"
        )
        return_value = bigcomm_app_client.delete_a_placement(
            placement_uuid=mock_placement_uuid,
        )
        assert return_value

    def test_get_all_orders(
        self, requests_mock: "RequestsMockFixture", bigcomm_app_client
    ):
        requests_mock.get(
            f"https://api.bigcommerce.com/stores/{bigcomm_app_client.store_hash}/v2/orders"
        )
        return_value = bigcomm_app_client.get_all_orders(
            min_date_created="yesterday", max_date_created="tomorrow"
        )
        assert return_value
