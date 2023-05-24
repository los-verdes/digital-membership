import pytest
from typing import TYPE_CHECKING
from member_card.models import AnnualMembership
from mock import sentinel
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
    app_client = bigcommerce.get_app_client_for_store()
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


@pytest.fixture()
def mock_order():
    mock_store_hash = "mock_store_hash"
    return {
        "id": 100,
        "customer_id": 20,
        "cart_id": 30,
        "date_created": "Wed, 10 Jan 2018 21:05:30 +0000",
        "date_modified": "Wed, 05 Dec 2018 20:16:55 +0000",
        "date_shipped": "",
        "status_id": 11,
        "status": "Awaiting Fulfillment",
        "billing_address": {
            "first_name": "Jane",
            "last_name": "Doe",
            "company": "",
            "street_1": "455 Main Street",
            "street_2": "",
            "city": "Austin",
            "state": "Texas",
            "zip": "78751",
            "country": "United States",
            "country_iso2": "US",
            "phone": "",
            "email": "janedoe@example.com",
            "form_fields": [],
        },
        "is_email_opt_in": False,
        "credit_card_type": None,
        "order_source": "manual",
        "channel_id": 1,
        "external_source": "POS",
        "products": {
            "url": f"https://api.bigcommerce.com/stores/{mock_store_hash}/v2/orders/100/products",
            "resource": "/orders/100/products",
        },
        "shipping_addresses": {
            "url": f"https://api.bigcommerce.com/stores/{mock_store_hash}/v2/orders/100/shippingaddresses",
            "resource": "/orders/100/shippingaddresses",
        },
        "coupons": {
            "url": f"https://api.bigcommerce.com/stores/{mock_store_hash}/v2/orders/100/coupons",
            "resource": "/orders/100/coupons",
        },
        "external_id": None,
        "external_merchant_id": {},
        "tax_provider_id": "BasicTaxProvider",
        "store_default_currency_code": "",
        "store_default_to_transactional_exchange_rate": "1.0000000000",
        "custom_status": "Awaiting Fulfillment",
        "customer_locale": "en",
        "external_order_id": "external-order-id",
    }


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


def test_insert_order_as_membership(app: "Flask", mock_order):
    with app.app_context():
        returned_membership_orders = bigcommerce.insert_order_as_membership(
            order=mock_order,
            order_products=[
                dict(
                    id=1,
                    product_id=123,
                    name="LOS VERDES TEST MEMBERSHIP!",
                    sku=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"][0],
                ),
            ],
            membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
        )

        assert len(returned_membership_orders) == 1

        order_instance = AnnualMembership.query.filter_by(
            order_id=f'{mock_order["id"]}_bc'
        ).one()
        assert order_instance.customer_email == mock_order["billing_address"]["email"]


def test_insert_shipped_order_as_membership(app: "Flask", mock_order):
    mock_order["date_shipped"] = "2023-01-02T11:22:33Z"
    with app.app_context():
        returned_membership_orders = bigcommerce.insert_order_as_membership(
            order=mock_order,
            order_products=[
                dict(
                    id=1,
                    product_id=123,
                    name="LOS VERDES TEST MEMBERSHIP!",
                    sku=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"][0],
                    product_options=[dict(id=1)],
                ),
            ],
            membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
        )

        assert len(returned_membership_orders) == 1

        order_instance = AnnualMembership.query.filter_by(
            order_id=f'{mock_order["id"]}_bc'
        ).one()
        assert order_instance.fulfilled_on is not None


def test_parse_subscription_orders(app: "Flask", mock_order, mocker):
    mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BiggercommerceApi")
    mock_bigcomm_api = mock_bigcomm_api_class()
    mock_bigcomm_api.OrderProducts.all.return_value = [
        dict(
            id=1,
            product_id=123,
            name="LOS VERDES TEST MEMBERSHIP!",
            sku=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"][0],
            product_options=[dict(id=1)],
        ),
    ]
    mock_order["date_shipped"] = "2023-01-02T11:22:33Z"
    with app.app_context():
        returned_membership_orders = bigcommerce.parse_subscription_orders(
            bigcommerce_client=mock_bigcomm_api,
            membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
            subscription_orders=[mock_order],
        )
        assert len(returned_membership_orders) == 1
        assert returned_membership_orders[0].fulfilled_on is not None


def test_load_all_bigcommerce_orders(app: "Flask", mocker):
    mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BiggercommerceApi")
    mock_bigcomm_api = mock_bigcomm_api_class()
    mock_load_orders = mocker.patch("member_card.bigcommerce.load_orders")
    mocker.patch("member_card.bigcommerce.parse_subscription_orders")
    bigcommerce.load_all_bigcommerce_orders(
        bigcommerce_client=mock_bigcomm_api,
        membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
    )
    mock_load_orders.assert_called_once_with(
        bigcommerce_client=mock_bigcomm_api,
        membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
    )


def test_load_single_order(app: "Flask", mock_order, mocker):
    mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BigcommerceApi")
    mock_bigcomm_api = mock_bigcomm_api_class()
    mock_parser_orders = mocker.patch(
        "member_card.bigcommerce.parse_subscription_orders"
    )
    mock_bigcomm_api.Orders.get.return_value = mock_order
    bigcommerce.load_single_order(
        bigcommerce_client=mock_bigcomm_api,
        membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
        order_id=mock_order["id"],
    )
    mock_bigcomm_api.Orders.get.assert_called_once_with(mock_order["id"])
    mock_parser_orders.assert_called_once_with(
        bigcommerce_client=mock_bigcomm_api,
        membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
        subscription_orders=[mock_order],
    )


def test_bigcommerce_orders_etl(app: "Flask", mock_order, mocker):
    mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BigcommerceApi")
    mock_bigcomm_api = mock_bigcomm_api_class()
    mock_load_orders = mocker.patch("member_card.bigcommerce.load_orders")
    mock_parser_orders = mocker.patch(
        "member_card.bigcommerce.parse_subscription_orders"
    )
    mock_bigcomm_api.Orders.get.return_value = mock_order

    with app.app_context():
        bigcommerce.bigcommerce_orders_etl(
            bigcommerce_client=mock_bigcomm_api,
            membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
        )
    mock_load_orders.assert_called_once()
    mock_parser_orders.assert_called_once()


def test_load_orders(app: "Flask", mock_order, mocker):
    mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BigcommerceApi")
    mock_bigcomm_api = mock_bigcomm_api_class()
    mock_bigcomm_api.Orders.iterall.return_value = sentinel.bigcomm_orders
    returned_orders = bigcommerce.load_orders(
        bigcommerce_client=mock_bigcomm_api,
        membership_skus=app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"],
    )
    assert sentinel.bigcomm_orders == returned_orders
    mock_bigcomm_api.Orders.iterall.assert_called_once()


def test_generate_webhook_token(app: "Flask", mocker):
    mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BigcommerceApi")
    mock_bigcomm_api = mock_bigcomm_api_class()

    with app.app_context():
        returned_token = bigcommerce.generate_webhook_token(api=mock_bigcomm_api)
    assert returned_token


class TestBigcommerceCustomerEtl:
    def test_no_matching_user(self, app: "Flask", mocker):
        mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BigcommerceApi")
        mock_bigcomm_api = mock_bigcomm_api_class()
        mock_customers_iterall = mock_bigcomm_api.Customers.iterall
        mock_customers_iterall.return_value = [
            dict(id=1000, email="los.verdes.tester.updated@gmail.com")
        ]

        with app.app_context():
            bigcommerce.customer_etl(
                bigcommerce_client=mock_bigcomm_api,
            )
        mock_customers_iterall.assert_called_once()

    def test_extant_user_by_email(self, app: "Flask", mocker, fake_user):
        mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BigcommerceApi")
        mock_bigcomm_api = mock_bigcomm_api_class()
        mock_customers_iterall = mock_bigcomm_api.Customers.iterall
        fake_user.bigcommerce_id = 0
        mock_customers_iterall.return_value = [
            dict(id=2, email="los.verdes.tester@gmail.com")
        ]

        with app.app_context():
            bigcommerce.customer_etl(
                bigcommerce_client=mock_bigcomm_api,
            )
        mock_customers_iterall.assert_called_once()

    def test_extant_user_by_id(self, app: "Flask", mocker, fake_user):
        mock_bigcomm_api_class = mocker.patch("member_card.bigcommerce.BigcommerceApi")
        mock_bigcomm_api = mock_bigcomm_api_class()
        mock_customers_iterall = mock_bigcomm_api.Customers.iterall
        mock_customers_iterall.return_value = [
            dict(id=1, email="los.verdes.tester.updated@gmail.com")
        ]

        with app.app_context():
            bigcommerce.customer_etl(
                bigcommerce_client=mock_bigcomm_api,
            )
        mock_customers_iterall.assert_called_once()
