import json
from typing import TYPE_CHECKING

from bigcommerce.api import BigcommerceApi
from flask.testing import FlaskClient

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

APP_SCOPES = [
    "store_v2_customers_login",
    "store_v2_customers_read_only",
    "store_v2_default",
    "store_v2_orders_read_only",
    "store_v2_products_read_only",
    "store_v2_transactions_read_only",
    "users_basic_information",
]


class TestUnauthenticatedRequests:
    def test_bigcommerce_callback(self, client: "FlaskClient"):
        response = client.get("/bigcommerce/callback")
        assert response.status_code == 400


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
