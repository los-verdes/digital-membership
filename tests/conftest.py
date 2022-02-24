import logging
from datetime import datetime, timezone

import flask_migrate
import pytest
from member_card import create_app
from member_card.db import db
from member_card.models.annual_membership import AnnualMembership
from member_card.models.user import User
from member_card.worker import worker_bp
from mock import Mock, patch

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope="session")
def app():
    app = create_app(env="tests")
    with app.app_context():
        flask_migrate.upgrade()

    app.register_blueprint(worker_bp)

    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def runner_without_db(app):
    sql_alchemy_ext = app.extensions["sqlalchemy"]
    del app.extensions["sqlalchemy"]

    yield app.test_cli_runner()

    app.extensions["sqlalchemy"] = sql_alchemy_ext


@pytest.fixture()
def authenticated_client(app, fake_user):
    mock_get_user = patch("flask_login.utils._get_user", Mock(return_value=fake_user))

    with app.app_context():
        app.login_manager._login_disabled = True
        mock_get_user.start()
        yield app.test_client()
        mock_get_user.stop()
        app.login_manager._login_disabled = False


@pytest.fixture()
def fake_user(app):
    """Create fake user optionally with roles"""
    user_cls = User
    email = "los.verdes.tester@gmail.com"
    userid = 1
    roles = None

    user = user_cls()
    user.email = email
    user.id = userid
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
def fake_membership_order(app, fake_user):
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
def fake_member(fake_user, fake_membership_order):
    fake_membership_order.user_id = fake_user.id
    db.session.add(fake_membership_order)
    db.session.commit()

    yield fake_user


# def set_current_user(login_manager, user):
#     """Set up so that when request is received,
#     the token will cause 'user' to be made the current_user
#     """

#     def token_cb(request):
#         if request.headers.get("Authentication-Token") == "token":
#             return user
#         return login_manager.anonymous_user()

#     login_manager.request_loader(token_cb)
