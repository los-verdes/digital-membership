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
from member_card.models import AppleDeviceRegistration
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
def user_datastore(app: "Flask") -> SQLAlchemySessionUserDatastore:
    user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
    return user_datastore


def create_fake_user(app: "Flask", email):
    # user_id = 1
    with app.app_context():
        if extant_user := User.query.filter_by(email=email).first():
            db.session.delete(extant_user)
            db.session.commit()
    user_cls = User

    user = user_cls()
    user.first_name = "Verde"
    user.last_name = "Tester"
    user.fullname = f"{user.first_name} {user.last_name}"
    user.email = email
    # user.id = user_id
    user.password = "mypassword"
    user.active = True
    return user


@pytest.fixture()
def fake_user(app: "Flask", user_datastore: SQLAlchemySessionUserDatastore) -> User:
    """Create fake user optionally with roles"""
    user = create_fake_user(
        app=app,
        email="los.verdes.tester@gmail.com",
    )

    with app.app_context():
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        yield user

        user = db.session.query(User).filter(User.id == user_id).first()
        if user:
            for role in user.roles:
                user_datastore.remove_role_from_user(user, role)
                role.users.remove(user)
                # db.session.add(user)
                db.session.add(role)
                db.session.commit()
            db.session.add(user)

            db.session.query(User).filter(User.id == user.id).first()
            db.session.delete(user)
            db.session.commit()


@pytest.fixture()
def fake_other_user(app: "Flask") -> User:
    user = create_fake_user(
        app=app,
        email="other-los.verdes.tester@gmail.com",
    )
    with app.app_context():

        db.session.add(user)
        db.session.commit()

        yield user

        db.session.delete(user)
        db.session.commit()


@pytest.fixture()
def fake_admin_role(
    app: "Flask", user_datastore: SQLAlchemySessionUserDatastore, fake_user
) -> Role:
    admin_role = user_datastore.find_or_create_role(
        name="admin",
        description="Administrators allowed to connect Squarespace extensions, etc.",
    )

    yield admin_role

    user_datastore.remove_role_from_user(fake_user, admin_role)
    db.session.delete(admin_role)
    db.session.commit()


@pytest.fixture()
def fake_admin_user(
    app: "Flask",
    user_datastore: SQLAlchemySessionUserDatastore,
    fake_user: User,
    fake_admin_role: Role,
) -> Role:
    fake_user.roles = [fake_admin_role]
    db.session.add(fake_user)
    db.session.commit()

    yield fake_user

    user_datastore.remove_role_from_user(fake_user, fake_admin_role)


@pytest.fixture()
def fake_membership_order(app: "Flask", fake_user: User) -> AnnualMembership:
    membership_order = AnnualMembership()

    today = datetime.utcnow().replace(tzinfo=timezone.utc)
    # one_year_from_now = today + timedelta(days=366)
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

        yield membership_order

        membership_order.user_id = None
        db.session.add(membership_order)
        db.session.commit()

        membership_order = (
            db.session.query(AnnualMembership).filter_by(id=membership_order.id).first()
        )
        db.session.delete(membership_order)
        db.session.commit()


@pytest.fixture()
def fake_member(fake_user: User, fake_membership_order: AnnualMembership) -> User:
    fake_membership_order.user_id = fake_user.id
    db.session.add(fake_membership_order)
    db.session.commit()

    yield fake_user

    fake_membership_order.user_id = None
    db.session.add(fake_membership_order)
    db.session.commit()


@pytest.fixture()
def fake_card(fake_member: User) -> MembershipCard:
    from member_card.models.membership_card import get_or_create_membership_card

    fake_membership_card = get_or_create_membership_card(fake_member)
    db.session.add(fake_membership_card)
    db.session.commit()

    yield fake_membership_card

    fake_membership_card.user_id = None
    db.session.query(AppleDeviceRegistration).filter_by(
        membership_card_id=fake_membership_card.id
    ).delete(synchronize_session="fetch")
    db.session.query(MembershipCard).filter_by(id=fake_membership_card.id).delete(
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
