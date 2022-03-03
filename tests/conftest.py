import contextlib
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import flask_migrate
import pytest
from flask.testing import FlaskClient, FlaskCliRunner
from flask_security import SQLAlchemySessionUserDatastore
from member_card import create_worker_app
from member_card.db import db
from member_card.models.annual_membership import AnnualMembership
from member_card.models.user import Role, User
from member_card.models.membership_card import MembershipCard
from mock import Mock, patch

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


@contextlib.contextmanager
def client_with_mock_user(app, user):
    mock_get_user = patch("flask_login.utils._get_user", Mock(return_value=user))

    with app.app_context():
        app.login_manager._login_disabled = True
        mock_get_user.start()
        yield app.test_client()
        mock_get_user.stop()
        app.login_manager._login_disabled = False


@pytest.fixture()
def authenticated_client(app: "Flask", fake_user):
    with client_with_mock_user(app, fake_user) as authenticated_client:
        yield authenticated_client


@pytest.fixture()
def admin_client(app: "Flask", fake_admin_user):
    with client_with_mock_user(app, fake_admin_user) as admin_client:
        yield admin_client


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

    user = user_cls()
    user.first_name = "Verde"
    user.last_name = "Tester"
    user.fullname = f"{user.first_name} {user.last_name}"
    user.email = email
    user.id = user_id
    user.password = "mypassword"
    user.active = True

    with app.app_context():

        db.session.add(user)
        db.session.commit()

        yield user

        db.session.delete(user)
        db.session.commit()


@pytest.fixture()
def fake_admin_role(app: "Flask") -> Role:
    user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
    admin_role = user_datastore.find_or_create_role(
        name="admin",
        description="Administrators allowed to connect Squarespace extensions, etc.",
    )
    yield admin_role
    db.session.delete(admin_role)
    db.session.commit()


@pytest.fixture()
def fake_admin_user(app: "Flask", fake_user: User, fake_admin_role: Role) -> Role:
    fake_user.roles = [fake_admin_role]
    db.session.add(fake_user)
    db.session.commit()

    yield fake_user

    fake_user.roles = []
    db.session.add(fake_user)
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


@pytest.fixture()
def fake_card(fake_member: User) -> MembershipCard:
    from member_card.models.membership_card import get_or_create_membership_card

    fake_membership_card = get_or_create_membership_card(fake_member)
    db.session.add(fake_membership_card)
    db.session.commit()

    yield fake_membership_card

    db.session.delete(fake_membership_card)
    db.session.commit()
