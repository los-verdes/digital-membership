import base64
import json
import logging

from bigcommerce import connection

from member_card import worker
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

logging.basicConfig(level=logging.DEBUG)


class TestPubsubIngress:
    @staticmethod
    def generate_test_envelope(message):
        test_envelope = dict(
            message=dict(
                data=base64.b64encode(json.dumps(message).encode("utf-8")).decode(
                    "utf-8"
                ),
            ),
        )
        return test_envelope

    def test_get_returns_method_not_allowed(self, client):
        response = client.get("/pubsub")
        logging.debug(f"{response=}")
        # Check that this method is indeed _not_ allowed
        assert response.status_code == 405

    def test_post_with_no_body(self, client):
        response = client.post("/pubsub")
        logging.debug(f"{response=}")

        # Check that we return a 400 / Bad Request in these cases
        assert response.status_code == 400

    def test_malformed_message_type(self, client):
        response = client.post(
            "/pubsub",
            json={"is hot garbage": True},
        )
        logging.debug(f"{response=}")

        # Check that we return a 400 / Bad Request in these cases
        assert response.status_code == 400

    def test_unsupported_message_type(self, client):
        test_message = dict(type="not-a-supported-type")
        response = client.post(
            "/pubsub",
            json=self.generate_test_envelope(test_message),
        )
        logging.debug(f"{response=}")

        # Check that we return a 400 / Bad Request in these cases
        assert response.status_code == 400

    def test_email_distribution_request(self, client):
        test_message = dict(
            type="email_distribution_request",
            email_distribution_recipient="los.verdes.tester+pls-no-matchy@gmail.com",
        )
        response = client.post(
            "/pubsub",
            json=self.generate_test_envelope(test_message),
        )
        logging.debug(f"{response=}")

        # Check that we return a 400 / Bad Request in these cases
        assert response.status_code == 204

    def test_sync_subscriptions_etl(self, client, mocker):
        mock_store_hash = "mock_store_hash"
        mock_orders = [
            {
                "id": 100,
                "customer_id": 20,
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
        ]
        mock_bigcomm_api = mocker.MagicMock()
        mock_bigcomm_api.connection = mocker.create_autospec(connection.Connection)
        mock_bigcomm_api.connection.store_hash = mock_store_hash

        # mock_bigcomm_api_orders = mocker.patch.object(mock_bigcomm_api, 'Orders')
        mock_orders_iterall = mocker.MagicMock()
        mock_orders_iterall.return_value = mock_orders
        mock_bigcomm_api.Orders.return_value = mock_orders_iterall

        mock_bigcomm = mocker.patch("member_card.worker.bigcommerce")
        mock_get_app_client_for_store = mock_bigcomm.get_app_client_for_store

        mock_get_app_client_for_store.return_value = mock_bigcomm_api
        mock_bigcommerce = mocker.patch("member_card.worker.bigcommerce")
        mock_bigcommerce_orders_etl = mock_bigcommerce.bigcommerce_orders_etl
        test_message = dict(
            type="sync_subscriptions_etl",
        )
        response = client.post(
            "/pubsub",
            json=self.generate_test_envelope(test_message),
        )
        logging.debug(f"{response=}")

        # Check that we return a 400 / Bad Request in these cases
        assert response.status_code == 204

        mock_bigcommerce_orders_etl.assert_called_once()

    # def test_sync_squarespace_order(self, app, client, mocker):
    #     mock_squarespace_class = mocker.patch("member_card.worker.Squarespace")
    #     mock_squarespace_client = mock_squarespace_class()
    #     mock_load_single_order = mocker.patch("member_card.worker.load_single_order")
    #     test_order_id = str(sentinel.squarespace_order_id)
    #     test_message = dict(
    #         type="sync_squarespace_order",
    #         order_id=test_order_id,
    #     )
    #     response = client.post(
    #         "/pubsub",
    #         json=self.generate_test_envelope(test_message),
    #     )
    #     logging.debug(f"{response=}")

    #     # Check that we return a 400 / Bad Request in these cases
    #     assert response.status_code == 204

    #     mock_load_single_order.assert_called_once_with(
    #         squarespace_client=mock_squarespace_client,
    #         membership_skus=app.config["SQUARESPACE_MEMBERSHIP_SKUS"],
    #         order_id=test_order_id,
    #     )


class TestEmailDistribution:
    def test_no_matching_user(self, mocker):
        mock_generate_email = mocker.patch("member_card.worker.generate_email_message")
        mock_send_email = mocker.patch("member_card.worker.send_email_message")
        test_message = dict(
            type="email_distribution_request",
            email_distribution_recipient="los.verdes.tester+pls-no-matchy@gmail.com",
        )

        return_value = worker.process_email_distribution_request(
            message=test_message,
        )
        logging.debug(f"{return_value=}")

        assert return_value is None

        mock_generate_email.assert_not_called()
        mock_send_email.assert_not_called()

    def test_with_matching_user_no_memberships(self, mocker, fake_user):
        mock_generate_email = mocker.patch("member_card.worker.generate_email_message")
        mock_send_email = mocker.patch("member_card.worker.send_email_message")
        test_message = dict(
            type="email_distribution_request",
            email_distribution_recipient=fake_user.email,
        )

        return_value = worker.process_email_distribution_request(
            message=test_message,
        )
        logging.debug(f"{return_value=}")

        assert return_value is None

        mock_generate_email.assert_not_called()
        mock_send_email.assert_not_called()

    def test_with_matching_user_with_memberships(self, mocker, fake_member):
        mock_upload_image = mocker.patch(
            "member_card.worker.ensure_uploaded_card_image"
        )
        mock_upload_apple_pass = mocker.patch(
            "member_card.worker.generate_and_upload_apple_pass"
        )
        mock_generate_email = mocker.patch("member_card.worker.generate_email_message")
        mock_send_email = mocker.patch("member_card.worker.send_email_message")
        test_message = dict(
            type="email_distribution_request",
            email_distribution_recipient=fake_member.email,
        )

        return_value = worker.process_email_distribution_request(
            message=test_message,
        )
        logging.debug(f"{return_value=}")

        assert return_value is mock_send_email.return_value

        mock_upload_image.assert_called_once()
        mock_upload_apple_pass.assert_called_once()

        mock_generate_email.assert_called_once()

        mock_send_email.assert_called_once_with(mock_generate_email.return_value)


class TestEnsureCardImage:
    def test_no_matching_user(self, mocker):
        mock_ensure_uploaded_card_image = mocker.patch(
            "member_card.worker.ensure_uploaded_card_image"
        )
        test_message = dict(
            type="ensure_uploaded_card_image_request",
            member_email_address="los.verdes.tester+pls-no-matchy@gmail.com",
        )

        return_value = worker.process_ensure_uploaded_card_image_request(
            message=test_message,
        )
        logging.debug(f"{return_value=}")

        assert return_value is None

        mock_ensure_uploaded_card_image.assert_not_called()

    def test_with_matching_user_no_memberships(self, mocker, fake_user):
        mock_ensure_uploaded_card_image = mocker.patch(
            "member_card.worker.ensure_uploaded_card_image"
        )
        test_message = dict(
            type="ensure_uploaded_card_image_request",
            member_email_address=fake_user.email,
        )

        return_value = worker.process_ensure_uploaded_card_image_request(
            message=test_message,
        )
        logging.debug(f"{return_value=}")

        assert return_value is mock_ensure_uploaded_card_image.return_value

        mock_ensure_uploaded_card_image.assert_called_once()

    def test_with_matching_user_with_memberships(self, mocker, fake_member):
        mock_ensure_uploaded_card_image = mocker.patch(
            "member_card.worker.ensure_uploaded_card_image"
        )
        test_message = dict(
            type="ensure_uploaded_card_image_request",
            member_email_address=fake_member.email,
        )

        return_value = worker.process_ensure_uploaded_card_image_request(
            message=test_message,
        )
        logging.debug(f"{return_value=}")

        mock_ensure_uploaded_card_image.assert_called_once()


def test_sync_bigcommerce_order(app: "Flask", mocker):
    mock_bigcommerce = mocker.patch("member_card.worker.bigcommerce")
    test_message = dict(
        type="sync_bigcommerce_order",
        store_hash=app.config["BIGCOMMERCE_STORE_HASH"],
        data=dict(id="test_sync_bigcommerce_order_id"),
    )

    membership_skus = app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"]

    with app.app_context():
        return_value = worker.sync_bigcommerce_order(
            message=test_message,
        )
    logging.debug(f"{return_value=}")

    assert return_value == "nah"

    mock_bigcommerce.load_single_order.assert_called_once_with(
        bigcommerce_client=mock_bigcommerce.get_app_client_for_store.return_value,
        membership_skus=membership_skus,
        order_id=test_message["data"]["id"],
    )


def test_worker_sync_customers_etl(mocker):
    mock_bigcommerce = mocker.patch("member_card.worker.bigcommerce")
    test_message = dict(
        type="sync_customers_etl",
    )

    return_value = worker.sync_customers_etl(
        message=test_message,
    )
    logging.debug(f"{return_value=}")

    assert return_value is None

    mock_bigcommerce.customer_etl.assert_called_once()


def test_worker_run_slack_members_etl(mocker):
    mock_slack = mocker.patch("member_card.worker.slack")
    test_message = dict(
        type="run_slack_members_etl",
    )

    return_value = worker.run_slack_members_etl(
        message=test_message,
    )
    logging.debug(f"{return_value=}")

    assert return_value

    mock_slack.slack_members_etl.assert_called_once()
