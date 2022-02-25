import logging

from member_card.app import commit_on_success


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
