from typing import TYPE_CHECKING

import uuid
from datetime import datetime, timezone
from member_card import db
from member_card.models import AnnualMembership

if TYPE_CHECKING:

    from flask import Flask
    from flask_security import SQLAlchemySessionUserDatastore
    from member_card.models import User
    from pytest_mock.plugin import MockerFixture


def test_datastore_find_user_by_id(
    user_datastore: "SQLAlchemySessionUserDatastore", fake_user: "User"
):
    found_user = user_datastore.find_user(id=fake_user.id)
    assert fake_user == found_user


def test_datastore_find_user_by_str_id(
    user_datastore: "SQLAlchemySessionUserDatastore", fake_user: "User"
):
    found_user = user_datastore.find_user(id=str(fake_user.id))
    assert fake_user == found_user


def test_get_gcp_sql_engine_creator(app: "Flask", mocker: "MockerFixture"):
    test_conn_string = "test-gcp-instance-connection-string"
    test_db_name = "test-db-name"
    test_db_user = "test-db-user"

    with app.app_context():
        engine_creator = db.get_gcp_sql_engine_creator(
            instance_connection_string=test_conn_string,
            db_name=test_db_name,
            db_user=test_db_user,
        )
    assert engine_creator


def test_get_db_connector_sans_password(app: "Flask", mocker: "MockerFixture"):
    mock_connector = mocker.patch("member_card.db.connector")
    mock_conn_obj = mock_connector.Connector.return_value
    test_conn_string = "test-gcp-instance-connection-string"
    test_db_name = "test-db-name"
    test_db_user = "test-db-user"

    with app.app_context():
        engine_creator = db.get_gcp_sql_engine_creator(
            instance_connection_string=test_conn_string,
            db_name=test_db_name,
            db_user=test_db_user,
        )

    assert engine_creator()
    mock_conn_obj.connect.assert_called_once_with(
        test_conn_string,
        "pg8000",
        user=test_db_user,
        db=test_db_name,
    )
    assert mock_conn_obj._enable_iam_auth


def test_get_db_connector_with_password(app: "Flask", mocker: "MockerFixture"):
    mock_connector = mocker.patch("member_card.db.connector")
    mock_conn_obj = mock_connector.Connector.return_value
    test_conn_string = "test-gcp-instance-connection-string"
    test_db_name = "test-db-name"
    test_db_user = "test-db-user"
    test_db_pass = "test-db-pass"

    with app.app_context():
        engine_creator = db.get_gcp_sql_engine_creator(
            instance_connection_string=test_conn_string,
            db_name=test_db_name,
            db_user=test_db_user,
            db_pass=test_db_pass,
        )

    assert engine_creator()
    mock_conn_obj.connect.assert_called_once_with(
        test_conn_string,
        "pg8000",
        user=test_db_user,
        db=test_db_name,
        password=test_db_pass,
    )
    assert mock_conn_obj._enable_iam_auth is not True


def test_get_or_update_for_updates(
    app: "Flask", fake_membership_order: AnnualMembership
):
    membership_kwargs = fake_membership_order.to_dict()
    del membership_kwargs["is_active"]
    test_channel_name_update_str = "test-get-or-update"
    membership_kwargs["channel_name"] = test_channel_name_update_str
    updated_membership = db.get_or_update(
        session=db.db.session,
        model=AnnualMembership,
        filters=["order_id", "order_number"],
        kwargs=membership_kwargs,
    )
    assert updated_membership.channel_name == test_channel_name_update_str


def test_get_or_update_for_creates(
    app: "Flask",
):
    membership_kwargs = {
        "order_number": str(uuid.uuid4())[:30],
        "order_id": str(uuid.uuid4())[:30],
        "created_on": datetime.utcnow().replace(tzinfo=timezone.utc),
    }

    with app.app_context():
        updated_membership = db.get_or_update(
            session=db.db.session,
            model=AnnualMembership,
            filters=["order_id", "order_number"],
            kwargs=membership_kwargs,
        )
    assert updated_membership.order_id == membership_kwargs["order_id"]
