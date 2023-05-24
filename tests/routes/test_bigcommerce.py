import json
from typing import TYPE_CHECKING
import pytest
from bigcommerce.api import BigcommerceApi
from flask.testing import FlaskClient
from member_card.routes.bigcommerce import InvalidBigCommerceWebhookSignature
from member_card.utils import sign

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture
    from flask import Flask

APP_SCOPES = [
    "store_v2_customers_login",
    "store_v2_customers_read_only",
    "store_v2_default",
    "store_v2_orders_read_only",
    "store_v2_products_read_only",
    "store_v2_transactions_read_only",
    "users_basic_information",
]


@pytest.fixture()
def inc_big_webhook_signature(app: "Flask") -> "FlaskClient":
    with app.app_context():
        configured_store_hash = app.config["BIGCOMMERCE_STORE_HASH"]
        configured_client_id = app.config["BIGCOMMERCE_CLIENT_ID"]
        expected_token_data = f"{configured_store_hash}.{configured_client_id}"
        signature = sign(expected_token_data).lower()
    return signature


@pytest.fixture()
def inc_webhook_payload(app: "Flask") -> "FlaskClient":
    configured_store_hash = app.config["BIGCOMMERCE_STORE_HASH"]
    return {
        "data": {
            "type": "type",
        },
        "hash": "hash",
        "producer": f"producer/{configured_store_hash}",
        "scope": "scope",
        "store_id": "store_id",
    }


class TestUnauthenticatedRequests:
    def test_bigcommerce_callback(self, client: "FlaskClient"):
        response = client.get("/bigcommerce/callback")
        assert response.status_code == 400

    def test_order_webhook_malformed(self, client: "FlaskClient"):
        with pytest.raises(InvalidBigCommerceWebhookSignature):
            response = client.post("/bigcommerce/order-webhook")
            assert response.status_code == 400

    def test_order_webhook_forbidden(
        self, inc_big_webhook_signature, client: "FlaskClient", mocker: "MockerFixture"
    ):
        mock_publish_message = mocker.patch(
            "member_card.routes.bigcommerce.publish_message"
        )
        response = client.post(
            "/bigcommerce/order-webhook",
            json={
                "data": {
                    "type": "type",
                },
                "hash": "hash",
                "producer": "producer/store_hash",
                "scope": "scope",
                "store_id": "store_id",
            },
            headers=dict(authorization=f"bearer {inc_big_webhook_signature}"),
        )
        assert response.status_code == 403
        mock_publish_message.assert_not_called()


class TestAuthenticatedRequests:
    def test_bigcommerce_callback(
        self, app, client: "FlaskClient", mocker: "MockerFixture"
    ):
        mock_bigcomm_api = mocker.create_autospec(BigcommerceApi)

        mocker.patch(
            "member_card.routes.bigcommerce.BigcommerceApi"
        ).return_value = mock_bigcomm_api

        mock_access_token = "SUPER SECRET ACCESS TOKEN"
        mock_token_blob = dict(
            access_token=mock_access_token,
            user=dict(
                id=1,
                username="itsametestio",
                email="testio@losverd.es",
            ),
        )
        mock_bigcomm_api.oauth_fetch_token.return_value = mock_token_blob

        response = client.get(
            "/bigcommerce/callback",
            follow_redirects=True,
            query_string={
                "account_uuid": "8bfecf30-b4fe-4b8b-aa27-d31b7070b64a",
                "code": "h1vh9xwvgneuw3667yufmfckwu1yly7",
                "context": "stores/hgp7pebwfj",
                "scope": " ".join(APP_SCOPES),
            },
            data=json.dumps({}),  # ref: https://stackoverflow.com/a/67992042
        )
        assert response.history[0].status_code == 302
        assert response.history[0].location.startswith(
            "https://"
        ), f"Expected `https://` scheme in redirect URL not found in {response.history[0].location=}!"

    def test_order_webhook_unhandled_message_type(
        self,
        inc_big_webhook_signature,
        inc_webhook_payload,
        client: "FlaskClient",
        mocker: "MockerFixture",
    ):
        mock_publish_message = mocker.patch(
            "member_card.routes.bigcommerce.publish_message"
        )
        response = client.post(
            "/bigcommerce/order-webhook",
            json=inc_webhook_payload,
            headers=dict(authorization=f"bearer {inc_big_webhook_signature}"),
        )
        assert response.status_code == 200
        mock_publish_message.assert_not_called()

    def test_order_webhook_success(
        self,
        inc_big_webhook_signature,
        inc_webhook_payload,
        client: "FlaskClient",
        mocker: "MockerFixture",
    ):
        mock_publish_message = mocker.patch(
            "member_card.routes.bigcommerce.publish_message"
        )
        inc_webhook_payload["data"]["type"] = "order"
        response = client.post(
            "/bigcommerce/order-webhook",
            json=inc_webhook_payload,
            headers=dict(authorization=f"bearer {inc_big_webhook_signature}"),
        )
        assert response.status_code == 200
        mock_publish_message.assert_called_once()
