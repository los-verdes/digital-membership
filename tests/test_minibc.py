from typing import TYPE_CHECKING

import pytest

from member_card import minibc

if TYPE_CHECKING:
    from flask import Flask


@pytest.fixture()
def mock_subscriptions():
    return [
        {
            "id": 1022,
            "order_id": 500001,
            "customer": {
                "id": 501,
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
            },
            "payment_method": {
                "id": 13741,
                "method": "credit_card",
                "credit_card": {
                    "type": "Visa",
                    "last_digits": "string",
                    "expiry_month": 7,
                    "expiry_year": 2024,
                },
                "billing_address": {
                    "first_name": "John",
                    "last_name": "Jones",
                    "street_1": "200 Yorkland Blvd.",
                    "street_2": "Unit 210",
                    "city": "Toronto",
                    "state": "Ontario",
                    "country_iso2": "CA",
                    "zip": "M2J5C1",
                },
                "config_id": 122,
            },
            "products": [
                {
                    "store_product_id": 4002,
                    "order_product_id": 12901,
                    "name": "T-Shirt of the Month",
                    "sku": "TEST-001",
                    "options": [
                        {
                            "option_id": 43,
                            "value": "112",
                            "display_name": "Size",
                            "display_value": "M",
                        }
                    ],
                    "quantity": 2,
                    "price": 6.49,
                    "total": 12.98,
                }
            ],
            "periodicity": {"frequency": 1, "unit": "month"},
            "subtotal": 12.98,
            "shipping_cost": 5,
            "total": 17.98,
            "status": "active",
            "shipping_address": {
                "street_1": "200 Yorkland Blvd.",
                "street_2": "Unit 210",
                "city": "Toronto",
                "state": "Ontario",
                "country_iso2": "CA",
                "zip": "M2J5C1,",
                "shipping_method": "Free Shipping",
            },
            "signup_date": "string",
            "pause_date": "string",
            "cancellation_date": "string",
            "next_payment_date": "2022-05-12",
            "created_time": "string",
            "last_modified": "string",
        }
    ]


def test_parse_subscriptions(app: "Flask", mock_subscriptions, mocker):
    with app.app_context():
        returned_subscriptions = minibc.parse_subscriptions(
            subscriptions=mock_subscriptions
        )
    assert len(returned_subscriptions) == 1
