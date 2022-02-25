import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from flask.testing import FlaskClient
from member_card.app import commit_on_success


def ensure_login_required(client: "FlaskClient", path, method="GET"):
    response = getattr(client, method.lower())(path=path)
    logging.debug(f"{response=}")
    # Check that we've been redirected to the login page:
    assert response.status_code == 302
    next_param = quote_plus(path)
    assert response.location == f"http://localhost/login?next={next_param}"


class TestUnauthenticatedRequests:
    def test_home_redirects_to_login_page(self, client: "FlaskClient"):
        ensure_login_required(client, path="/", method="GET")

    def test_login_page(self, client: "FlaskClient"):
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

    def test_home_route_with_active_membership(self, authenticated_client, fake_member):

        response = authenticated_client.get("/")
        logging.debug(response)

        soup = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

        card_actions_classes = [
            "save-google-pass-button",
            "save-apple-pass-button",
            "update-name-dialog-link",
        ]
        for card_actions_class in card_actions_classes:
            matching_buttons = soup.find_all("a", {"class": card_actions_class})
            logging.debug(matching_buttons)
            assert len(matching_buttons) > 0

        assert (
            soup.find(id="membership-primary-info-text").text.strip()
            == fake_member.fullname
        )


def test_db_commit_on_teardown(app, client, mocker):
    from member_card.db import db

    mock_session = mocker.patch.object(db, "session")

    mock_session.start()

    client.get("/")

    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()
    mock_session.remove.assert_called()
    mock_session.stop()


def test_db_teardown_rollback_on_error(client, mocker):
    from member_card.db import db

    assert client

    mock_session = mocker.patch.object(db, "session")

    mock_session.start()
    logging.warning(f"test_db_error_on_teardown(): {id(mock_session)=}")
    commit_on_success(Exception("just for testing tho"))

    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_called_once()
    mock_session.remove.assert_called()
    mock_session.stop()
