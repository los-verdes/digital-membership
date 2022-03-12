import json
from typing import TYPE_CHECKING

from member_card import sendgrid
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

if TYPE_CHECKING:
    from flask import Flask
    from member_card.models import MembershipCard
    from pytest_mock.plugin import MockerFixture


def test_generate_email_message(fake_card: "MembershipCard"):
    card_image_url = "test-card_image_url"
    apple_pass_url = "test-apple_pass_url"
    fake_card._google_pay_jwt = "test_google_pay_jwt"

    message = sendgrid.generate_email_message(
        membership_card=fake_card,
        card_image_url=card_image_url,
        apple_pass_url=apple_pass_url,
    )

    assert isinstance(message, Mail)


def test_send_email_message(
    app: "Flask", fake_card: "MembershipCard", mocker: "MockerFixture"
):
    mock_sg_client = mocker.create_autospec(SendGridAPIClient, instance=True)
    mocker.patch("member_card.sendgrid.SendGridAPIClient").return_value = mock_sg_client
    to_emails = fake_card.user.email
    test_message = Mail(
        from_email=app.config["EMAIL_FROM_ADDRESS"],
        to_emails=to_emails,
    )

    test_message.dynamic_template_data = {
        "subject": app.config["EMAIL_SUBJECT_TEXT"],
    }

    with app.app_context():
        # in app context cause method being called depends on some implicit current_app.config bits...
        return_value = sendgrid.send_email_message(test_message)

    assert return_value is not None
    mock_sg_client.send.assert_called_once_with(test_message)


def test_update_sendgrid_template(app: "Flask", mocker: "MockerFixture"):
    template_id = "test-template-id"
    test_template_version = dict(
        id="test-version-id",
        html_content="<hi></hi>",
        plain_content="HI! :)",
        editor="cats-editor",
    )
    test_template = {
        "versions": [test_template_version],
    }
    app.config["SENDGRID_TEMPLATE_ID"] = template_id
    # mock_sg_client = mocker.create_autospec(BaseInterface, instance=True)
    # mocker.patch("member_card.sendgrid.SendGridAPIClient").return_value = mock_sg_client
    mock_sg_class = mocker.patch("member_card.sendgrid.SendGridAPIClient")
    mock_sg = mock_sg_class.return_value

    mock_template_req = mock_sg.client.templates._.return_value

    mock_template_get = mock_template_req.get.return_value
    mock_template_get.body.decode.return_value = json.dumps(test_template)

    # mock_template_req.versions._().patch.return_value = json.dumps(test_patch_resp)

    with app.app_context():
        # in app context cause method being called depends on some implicit current_app.config bits...
        return_value = sendgrid.update_sendgrid_template()

    assert return_value is not None
    assert mock_sg_class.call_args_list
