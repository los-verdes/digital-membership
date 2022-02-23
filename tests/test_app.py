import logging


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
