import logging

import pytest
from member_card import create_app


@pytest.fixture(scope="session")
def app():
    app = create_app(env="tests")
    app.config.update(
        {
            "TESTING": True,
        }
    )

    # other setup can go here

    yield app

    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


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
