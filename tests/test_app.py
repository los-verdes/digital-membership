import logging
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from flask.testing import FlaskClient
from member_card import utils
from member_card.app import commit_on_success, recaptcha
from member_card.models.user import User

if TYPE_CHECKING:
    from flask import Flask
    from pytest_mock.plugin import MockerFixture


def assert_form_error_message(response, expected_msg):
    assert response.status_code == 200

    soup = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    form_error_message_element = soup.find(id="form-error-message")
    assert form_error_message_element
    assert form_error_message_element.text.strip() == expected_msg


def ensure_login_required(client: "FlaskClient", path, method="GET"):
    response = getattr(client, method.lower())(path=path)
    logging.debug(f"{response=}")
    # Check that we've been redirected to the login page:
    assert response.status_code == 302
    next_param = quote_plus(path)
    assert response.location == f"http://localhost/login?next={next_param}"


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


class TestUnauthenticatedRequests:
    def test_home_redirects_to_login_page(self, client: "FlaskClient"):
        ensure_login_required(client, path="/", method="GET")

    def test_login_page(self, client: "FlaskClient"):
        response = client.get("/login")
        assert b'<form id="emailDistributionRequestForm"' in response.data
        assert b' id="appleid-signin" ' in response.data
        assert b' id="yahoo-oauth2-button" ' in response.data
        assert b' id="google-oauth2-button" ' in response.data

    def test_edit_user_name_invalid_method(self, client: "FlaskClient"):
        response = client.get("/edit-user-name")
        # Check that this method is indeed _not_ allowed
        assert response.status_code == 405

    def test_edit_user_name(self, client: "FlaskClient"):
        ensure_login_required(client, path="/edit-user-name", method="POST")

    def test_passes_google_pay_redirects_to_login_page(self, client: "FlaskClient"):
        ensure_login_required(client, path="/passes/google-pay", method="GET")

    def test_passes_apple_pay_redirects_to_login_page(self, client: "FlaskClient"):
        ensure_login_required(client, path="/passes/apple-pay", method="GET")

    def test_squarespace_login(self, client: "FlaskClient"):
        ensure_login_required(client, path="/squarespace/oauth/login", method="GET")

    def test_squarespace_oauth_callback(self, client: "FlaskClient"):
        ensure_login_required(client, path="/squarespace/oauth/connect", method="GET")


class TestAuthenticatedRequests:
    def test_modify_session(self, app, authenticated_client):

        response = authenticated_client.get("/", follow_redirects=True)

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

    def test_edit_user_name_by_inactive_member(
        self, app: "Flask", authenticated_client: "FlaskClient", fake_user: "User"
    ):
        self.assert_edit_user_name_success(app, authenticated_client, fake_user)

    def test_edit_user_name_by_active_member(
        self, app: "Flask", authenticated_client: "FlaskClient", fake_member: "User"
    ):
        self.assert_edit_user_name_success(app, authenticated_client, fake_member)

    def assert_edit_user_name_success(self, app, authenticated_client, fake_user):
        new_first_name = "You done"
        new_last_name = "Been Edited"
        new_fullname = f"{new_first_name} {new_last_name}"
        response = authenticated_client.post(
            "/edit-user-name",
            data=dict(
                newFirstName=new_first_name,
                newLastName=new_last_name,
            ),
            follow_redirects=True,
        )
        assert response.status_code == 200

        soup = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
        form_message_element = soup.find(id="form-message")
        assert form_message_element
        assert form_message_element.text.strip() == utils.get_message_str(
            "edit_user_name_success"
        )

        with app.app_context():
            updated_fake_user = User.query.filter_by(id=fake_user.id).one()
        assert updated_fake_user.first_name == new_first_name
        assert updated_fake_user.last_name == new_last_name
        assert updated_fake_user.fullname == new_fullname

    def test_email_distribution_request_recaptcha_unverified(
        self, authenticated_client, mocker
    ):
        mock_publish_message = mocker.patch("member_card.app.publish_message")
        response = authenticated_client.post(
            "/email-distribution-request",
            follow_redirects=True,
        )
        mock_publish_message.assert_not_called()
        assert_form_error_message(
            response=response,
            expected_msg=utils.get_message_str("captcha_not_verified"),
        )

    def test_email_distribution_request_missing_recipient(
        self, authenticated_client, mocker
    ):
        mocker.patch.object(recaptcha, "verify", return_value=True)
        mock_publish_message = mocker.patch("member_card.app.publish_message")
        response = authenticated_client.post(
            "/email-distribution-request",
            follow_redirects=True,
        )
        mock_publish_message.assert_not_called()
        assert_form_error_message(
            response=response,
            expected_msg=utils.get_message_str("missing_email_distribution_recipient"),
        )

    def test_email_distribution_request_invalid_recipient(
        self, authenticated_client, mocker
    ):
        mocker.patch.object(recaptcha, "verify", return_value=True)
        mock_publish_message = mocker.patch("member_card.app.publish_message")
        response = authenticated_client.post(
            "/email-distribution-request",
            data=dict(
                emailDistributionRecipient="an-invalid-email-address",
            ),
            follow_redirects=True,
        )
        mock_publish_message.assert_not_called()
        assert response.status_code == 200
        soup = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
        form_error_message_element = soup.find(id="form-error-message")
        assert form_error_message_element
        expected_msg = (
            "The email address is not valid. It must have exactly one @-sign."
        )
        assert_form_error_message(response, expected_msg)
        assert form_error_message_element.text.strip() == expected_msg

    def test_email_distribution_request_valid_recipient(
        self, authenticated_client: "FlaskClient", fake_member: "User", mocker
    ):
        mocker.patch.object(recaptcha, "verify", return_value=True)
        mock_publish_message = mocker.patch("member_card.app.publish_message")
        response = authenticated_client.post(
            "/email-distribution-request",
            data=dict(
                emailDistributionRecipient=fake_member.email,
            ),
            follow_redirects=True,
        )
        assert response.status_code == 200

        mock_publish_message.assert_called_once()
        mock_publish_message.call_args.kwargs["message_data"][
            "type"
        ] == "email_distribution_request"
        mock_publish_message.call_args.kwargs["message_data"][
            "email_distribution_recipient"
        ] == fake_member.email

    def test_passes_google_pay_no_active_membership(
        self,
        authenticated_client: "FlaskClient",
        fake_user: "User",
        mocker: "MockerFixture",
    ):
        # mock_get_card.return_value
        mock_generate_pass_jwt = mocker.patch(
            "member_card.models.membership_card.generate_pass_jwt"
        )
        response = authenticated_client.get("/passes/google-pay")

        mock_generate_pass_jwt.assert_not_called()
        assert response.location == "http://localhost/no-active-membership-found"

    def test_passes_google_pay_with_active_membership(
        self,
        authenticated_client: "FlaskClient",
        fake_card,
        mocker: "MockerFixture",
    ):
        # mock_get_card.return_value
        mock_generate_pass_jwt = mocker.patch(
            "member_card.models.membership_card.generate_pass_jwt"
        )
        fake_jwt_str = "jwtest"
        fake_jwt_bytes = fake_jwt_str.encode("utf-8")
        mock_generate_pass_jwt.return_value = fake_jwt_bytes
        response = authenticated_client.get("/passes/google-pay")

        mock_generate_pass_jwt.assert_called_once_with(fake_card)
        assert response.location == f"https://pay.google.com/gp/v/save/{fake_jwt_str}"

    def test_passes_apple_pay_no_active_membership(
        self,
        authenticated_client: "FlaskClient",
        mocker: "MockerFixture",
    ):
        mock_get_apple_pass_for_user = mocker.patch(
            "member_card.app.get_apple_pass_for_user"
        )
        response = authenticated_client.get("/passes/apple-pay")

        mock_get_apple_pass_for_user.assert_not_called()
        assert response.location == "http://localhost/no-active-membership-found"

    def test_passes_apple_pay_with_active_membership(
        self,
        authenticated_client: "FlaskClient",
        fake_card,
        mocker: "MockerFixture",
        tmpdir,
    ):
        mock_get_apple_pass_for_user = mocker.patch(
            "member_card.app.get_apple_pass_for_user"
        )
        fake_pkpass_content = "<insert pass here>"
        p = tmpdir.join("path.pkpass")
        p.write(fake_pkpass_content)
        fake_pkpass_path = p.strpath
        mock_get_apple_pass_for_user.return_value = fake_pkpass_path
        response = authenticated_client.get("/passes/apple-pay")
        assert fake_pkpass_content.encode("utf-8") in response.data
        assert response.headers["Content-Type"] == "application/vnd.apple.pkpass"
        mock_get_apple_pass_for_user.assert_called_once_with(
            user=fake_card.user,
            membership_card=fake_card,
        )

    def test_squarespace_oauth_login(
        self,
        authenticated_client: "FlaskClient",
    ):
        response = authenticated_client.get("/squarespace/oauth/login")
        assert response.status_code == 302
        assert response.location == "http://localhost/"

    def test_squarespace_oauth_callback(
        self,
        authenticated_client: "FlaskClient",
    ):
        response = authenticated_client.get("/squarespace/oauth/connect")
        assert response.status_code == 302
        assert response.location == "http://localhost/"


class TestSquarespaceOauth:
    def test_squarespace_oauth_login(
        self,
        admin_client: "FlaskClient",
        mocker: "MockerFixture",
    ):
        mock_gen_auth_url = mocker.patch("member_card.app.generate_oauth_authorize_url")
        test_auth_url_str = (
            "http://localhost/this-would-redirect-to-squarespace-in-an-un-test"
        )
        mock_gen_auth_url.return_value = test_auth_url_str
        response = admin_client.get("/squarespace/oauth/login")
        assert response.status_code == 302
        assert response.location == test_auth_url_str

    def test_squarespace_oauth_callback_error_in_args(
        self,
        admin_client: "FlaskClient",
    ):
        response = admin_client.get(
            "/squarespace/oauth/connect?error=literally-anything-for-this-param",
            follow_redirects=True,
        )
        assert response.history[0].status_code == 302
        assert response.history[0].location.startswith(
            "http://localhost/squarespace/extension-details?"
        )
        assert_form_error_message(
            response=response,
            expected_msg=utils.get_message_str("squarespace_oauth_connect_error"),
        )

    def test_squarespace_oauth_callback_missing_state(
        self,
        admin_client: "FlaskClient",
    ):
        response = admin_client.get(
            "/squarespace/oauth/connect",
            follow_redirects=True,
        )
        assert response.history[0].status_code == 302
        assert response.history[0].location.startswith(
            "http://localhost/squarespace/extension-details?"
        )
        assert_form_error_message(
            response=response,
            expected_msg=utils.get_message_str(
                "squarespace_oauth_connect_missing_state"
            ),
        )

    def test_squarespace_oauth_callback(
        self,
        admin_client: "FlaskClient",
    ):

        with admin_client.session_transaction() as session:
            session["state"] = "test-state..."
        response = admin_client.get(
            f"/squarespace/oauth/connect?state={session['state']}",
            follow_redirects=True,
        )
        assert response.history[0].status_code == 302
        assert response.history[0].location.startswith(
            "http://localhost/squarespace/extension-details?"
        )
        assert_form_error_message(
            response=response,
            expected_msg=utils.get_message_str("squarespace_oauth_state_mismatch"),
        )
