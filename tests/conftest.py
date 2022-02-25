import logging
from datetime import datetime, timezone

import flask_migrate
import pytest
from member_card import create_worker_app
from member_card.db import db
from member_card.models.annual_membership import AnnualMembership
from member_card.models.user import User
from mock import Mock, patch
from flask.testing import FlaskClient, FlaskCliRunner
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope="session")
def app() -> "Flask":
    # Don't need to trace our tests typically so mocking this bit out :P
    with patch("member_card.monitoring", autospec=True):
        app = create_worker_app(env="tests")

    with app.app_context():
        flask_migrate.upgrade()

    yield app


@pytest.fixture()
def client(app: "Flask") -> "FlaskClient":
    return app.test_client()


@pytest.fixture()
def runner(app: "Flask") -> "FlaskCliRunner":
    return app.test_cli_runner()


@pytest.fixture()
def runner_without_db(app: "Flask"):
    sql_alchemy_ext = app.extensions["sqlalchemy"]
    del app.extensions["sqlalchemy"]

    yield app.test_cli_runner()

    app.extensions["sqlalchemy"] = sql_alchemy_ext


@pytest.fixture()
def authenticated_client(app: "Flask", fake_user):
    mock_get_user = patch("flask_login.utils._get_user", Mock(return_value=fake_user))

    with app.app_context():
        app.login_manager._login_disabled = True
        mock_get_user.start()
        yield app.test_client()
        mock_get_user.stop()
        app.login_manager._login_disabled = False


@pytest.fixture()
def fake_user(app: "Flask") -> User:
    """Create fake user optionally with roles"""
    user_id = 1
    with app.app_context():
        if extant_user := User.query.filter_by(id=user_id).first():
            db.session.delete(extant_user)
            db.session.commit()
    user_cls = User
    email = "los.verdes.tester@gmail.com"
    roles = None

    user = user_cls()
    user.first_name = "Verde"
    user.last_name = "Tester"
    user.fullname = f"{user.first_name} {user.last_name}"
    user.email = email
    user.id = user_id
    user.password = "mypassword"
    user.active = True
    if roles:
        if isinstance(roles, list):
            user.roles = roles
        else:
            user.roles = [roles]

    with app.app_context():

        db.session.add(user)
        db.session.commit()

        yield user

        db.session.delete(user)
        db.session.commit()


@pytest.fixture()
def fake_membership_order(app: "Flask", fake_user: User) -> AnnualMembership:
    membership_order = AnnualMembership()

    today = datetime.utcnow().replace(tzinfo=timezone.utc)
    # one_year_from_now = today + timedelta(days=366)
    membership_order.created_on = today
    with app.app_context():

        db.session.add(membership_order)
        db.session.commit()

        yield membership_order

        db.session.delete(membership_order)
        db.session.commit()


@pytest.fixture()
def fake_member(fake_user: User, fake_membership_order: AnnualMembership) -> User:
    fake_membership_order.user_id = fake_user.id
    db.session.add(fake_membership_order)
    db.session.commit()

    yield fake_user
