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
        # mock_futures = mocker.patch("member_card.gcp.futures")

        mock_bigcomm_api = mocker.create_autospec(BigcommerceApi)
        mocker.patch(
            "member_card.routes.bigcommerce.BigcommerceApi"
        ).return_value = mock_bigcomm_api
        # mock_bigcomm_api_class = mocker.patch("member_card.routes.bigcommerce.BigcommerceApi")
        response = client.get(
            "/bigcommerce/callback",
            data={
                "account_uuid": "8bfecf30-b4fe-4b8b-aa27-d31b7070b64a",
                "code": "h1vh9xwvgneuw3667yufmfckwu1yly7",
                "context": "stores/hgp7pebwfj",
                "scope": " ".join(APP_SCOPES),
            },
        )
        assert response
        # raise Exception(response)

        # from flask_security.core import current_user as current_login_user

        # with app.app_context():
        #     assert current_login_user is None

        # mock_bigcomm_api.oauth_fetch_token.assert_called_once()
        # assert response == 'cats'
