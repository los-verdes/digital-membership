import contextlib
import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import flask_migrate
import pytest
from flask.testing import FlaskClient, FlaskCliRunner
from flask_security import SQLAlchemySessionUserDatastore
from member_card import create_worker_app
from member_card.db import db
from member_card.models.annual_membership import AnnualMembership
from member_card.models.membership_card import MembershipCard
from member_card.models import AppleDeviceRegistration, SlackUser, StoreUser
from member_card.models.user import Role, User
from mock import Mock, patch
from PIL import Image

if TYPE_CHECKING:
    from flask import Flask


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


@pytest.fixture(scope="session")
def app() -> "Flask":
    # Don't need to trace our tests typically so mocking this bit out :P
    with patch("member_card.monitoring", autospec=True):
        app = create_worker_app(env="tests")

    with app.app_context():
        flask_migrate.upgrade()
    app.config["SERVER_NAME"] = "localhost"
    yield app

    with app.app_context():
        MembershipCard.query.delete()
        AnnualMembership.query.delete()
        SlackUser.query.delete()
        StoreUser.query.delete()

        user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
        for user in User.query.all():
            for role in list(user.roles):
                user_datastore.remove_role_from_user(user, role)
        db.session.commit()
        User.query.delete()
        db.session.commit()


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
    """
    Returns a test client with the given user pre-authenticated.

    Uses db.session.merge() to re-attach the (possibly expunged) user object
    to the current SQLAlchemy 2.0 session before mocking flask-login's user
    lookup, avoiding "already attached to session" errors across contexts.
    """
    with app.app_context():
        merged_user = db.session.merge(user)
        db.session.commit()
        mock_get_user = patch("flask_login.utils._get_user", Mock(return_value=merged_user))
        app.config["LOGIN_DISABLED"] = True
        mock_get_user.start()
        yield app.test_client()
        mock_get_user.stop()
        app.config["LOGIN_DISABLED"] = False


@pytest.fixture()
def authenticated_client(app: "Flask", fake_user):
    with client_with_mock_user(app, fake_user) as authenticated_client:
        yield authenticated_client


@pytest.fixture()
def admin_client(app: "Flask", fake_admin_user):
    with client_with_mock_user(app, fake_admin_user) as admin_client:
        yield admin_client


@pytest.fixture()
def user_datastore(app: "Flask") -> SQLAlchemySessionUserDatastore:
    with app.app_context():
        datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
    return datastore


def create_fake_user(app: "Flask", email, bigcommerce_id=1):
    with app.app_context():
        if extant_user := User.query.filter_by(email=email).first():
            db.session.delete(extant_user)
            db.session.commit()

    user = User()
    user.first_name = "Verde"
    user.last_name = "Tester"
    user.fullname = f"{user.first_name} {user.last_name}"
    user.email = email
    user.password = "mypassword"
    user.active = True
    user.bigcommerce_id = bigcommerce_id
    return user


@pytest.fixture()
def fake_user(app: "Flask") -> User:
    """Create a fake user and persist it; yield as a detached object."""
    user = create_fake_user(app=app, email="los.verdes.tester@gmail.com")

    with app.app_context():
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        # Eagerly load all relationships before detaching so they're accessible
        # on the plain Python object without an active session.
        _ = list(user.roles)
        _ = list(user.annual_memberships)
        _ = list(user.membership_cards)
        db.session.expunge(user)

    yield user

    with app.app_context():
        user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
        fresh = db.session.get(User, user_id)
        if fresh:
            for role in list(fresh.roles):
                user_datastore.remove_role_from_user(fresh, role)
            db.session.commit()
            db.session.delete(fresh)
            db.session.commit()


@pytest.fixture()
def fake_other_user(app: "Flask") -> User:
    user = create_fake_user(app=app, email="other-los.verdes.tester@gmail.com")

    with app.app_context():
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge(user)

    yield user

    with app.app_context():
        fresh = db.session.get(User, user_id)
        if fresh:
            db.session.delete(fresh)
            db.session.commit()


@pytest.fixture()
def fake_admin_role(app: "Flask", fake_user: User) -> Role:
    with app.app_context():
        user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
        admin_role = user_datastore.find_or_create_role(
            name="admin",
            description="Administrators allowed to connect Squarespace extensions, etc.",
        )
        db.session.commit()
        role_id = admin_role.id
        db.session.expunge(admin_role)

    yield admin_role

    with app.app_context():
        user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
        fresh_user = db.session.merge(fake_user)
        fresh_role = db.session.get(Role, role_id)
        if fresh_role and fresh_user:
            user_datastore.remove_role_from_user(fresh_user, fresh_role)
            db.session.commit()
            db.session.delete(fresh_role)
            db.session.commit()


@pytest.fixture()
def fake_admin_user(
    app: "Flask",
    fake_user: User,
    fake_admin_role: Role,
) -> User:
    with app.app_context():
        user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
        fresh_user = db.session.merge(fake_user)
        fresh_role = db.session.merge(fake_admin_role)
        user_datastore.add_role_to_user(fresh_user, fresh_role)
        db.session.commit()
        _ = list(fresh_user.roles)
        db.session.expunge(fresh_user)

    yield fresh_user

    with app.app_context():
        user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
        fresh_user = db.session.merge(fake_user)
        fresh_role = db.session.merge(fake_admin_role)
        user_datastore.remove_role_from_user(fresh_user, fresh_role)
        db.session.commit()


@pytest.fixture()
def fake_membership_order(app: "Flask", fake_user: User) -> AnnualMembership:
    membership_order = AnnualMembership()
    today = datetime.utcnow().replace(tzinfo=timezone.utc)
    membership_order.created_on = today
    membership_order.order_number = str(uuid.uuid4())[:30]
    membership_order.order_id = str(uuid.uuid4())[:30]
    membership_order.user_id = fake_user.id
    membership_order.customer_email = fake_user.email
    membership_order.channel_name = "test-fixture"
    membership_order.fulfillment_status = "PENDING"

    with app.app_context():
        db.session.add(membership_order)
        db.session.commit()
        order_id = membership_order.id
        _ = membership_order.user  # eagerly load
        db.session.expunge(membership_order)

    yield membership_order

    with app.app_context():
        order = db.session.get(AnnualMembership, order_id)
        if order:
            order.user_id = None
            db.session.commit()
            db.session.delete(order)
            db.session.commit()


@pytest.fixture()
def fake_member(app: "Flask", fake_user: User, fake_membership_order: AnnualMembership) -> User:
    with app.app_context():
        order = db.session.merge(fake_membership_order)
        order.user_id = fake_user.id
        db.session.commit()
        # Reload the user with fresh relationships
        fresh_user = db.session.get(User, fake_user.id)
        _ = list(fresh_user.annual_memberships)
        _ = list(fresh_user.membership_cards)
        _ = list(fresh_user.roles)
        db.session.expunge(fresh_user)

    yield fresh_user


@pytest.fixture()
def fake_card(app: "Flask", fake_member: User) -> MembershipCard:
    from member_card.models.membership_card import get_or_create_membership_card

    with app.app_context():
        fresh_member = db.session.merge(fake_member)
        db.session.commit()
        fake_membership_card = get_or_create_membership_card(fresh_member)
        db.session.add(fake_membership_card)
        db.session.commit()
        fake_membership_card_id = fake_membership_card.id
        # Refresh ensures all column attributes are loaded before expunge
        db.session.refresh(fake_membership_card)
        _ = fake_membership_card.user
        db.session.expunge(fake_membership_card)

    yield fake_membership_card

    with app.app_context():
        db.session.query(AppleDeviceRegistration).filter_by(
            membership_card_id=fake_membership_card_id
        ).delete(synchronize_session="fetch")
        db.session.query(MembershipCard).filter_by(id=fake_membership_card_id).delete(
            synchronize_session="fetch"
        )
        db.session.commit()


def get_test_file_path(filename):
    return os.path.join(BASE_DIR, "files", filename)


@pytest.fixture()
def untrimmed_with_bg_img() -> "Image":
    return Image.open(get_test_file_path("untrimmed_with_bg_img.png"))


@pytest.fixture()
def untrimmed_img() -> "Image":
    return Image.open(get_test_file_path("untrimmed_img.png"))
