import logging

import pytest
from member_card import create_app
import flask_migrate
from member_card.models.user import User, Role
from tests import utils
from mock import patch, Mock


@pytest.fixture(scope="session")
def app():
    app = create_app(env="tests")
    app.config.update(
        {
            "TESTING": True,
        }
    )

    with app.app_context():
        flask_migrate.upgrade()

    yield app

    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def authenticated_client(app):
    # with client.session_transaction() as session:
    #     # set a user id without going through the login route
    #     session["user_id"] = 1

    # # session is saved now

    user = utils.create_fake_user(User, roles=utils.create_fake_role(Role, "basic"))
    # utils.set_current_user(login_manager, user)
    mock_get_user = patch("flask_login.utils._get_user", Mock(return_value=user))

    with app.app_context():
        app.login_manager._login_disabled = True
        mock_get_user.start()
        yield app.test_client()
        mock_get_user.stop()
        app.login_manager._login_disabled = False


class TestUnauthenticatedRequests:
    def test_home_redirects_to_login_page(self, client):
        response = client.get("/")
        logging.debug(f"{response=}")
        # Check that we've been redirected to the login page:
        assert response.status_code == 302
        assert response.location == "http://localhost/login?next=%2F"

    def test_login_page(self, client):
        response = client.get("/login")
        assert b'<form id="emailDistributionRequestForm"' in response.data
        assert b' id="appleid-signin" ' in response.data
        assert b' id="yahoo-oauth2-button" ' in response.data
        assert b' id="google-oauth2-button" ' in response.data


class TestAuthenticatedRequests:
    def test_modify_session(self, app, authenticated_client):

        response = authenticated_client.get("/")

        from flask_security.core import current_user as current_login_user

        with app.app_context():
            assert current_login_user
        assert b"los.verdes.tester@gmail.com" in response.data
