from typing import TYPE_CHECKING

from slack_sdk import WebClient
from slack_sdk.web import SlackResponse
from member_card import slack

if TYPE_CHECKING:
    from flask import Flask
    from pytest_mock.plugin import MockerFixture


def test_get_web_client(app: "Flask"):
    with app.app_context():
        assert slack.get_web_client()


def test_slack_members_generator(app: "Flask", mocker: "MockerFixture"):
    mock_client = mocker.create_autospec(WebClient, instance=True)
    test_chunk_size = 2
    test_next_cursor = "mock_second_resp"
    mock_client.users_list.side_effect = [
        SlackResponse(
            client=mock_client,
            http_verb="get",
            api_url=dict(),
            req_args=dict(),
            data=dict(
                ok=True,
                members=["gracky", "verdisimossimo"],
                response_metadata=dict(next_cursor=test_next_cursor),
            ),
            headers=dict(),
            status_code=200,
        ),
        SlackResponse(
            client=mock_client,
            http_verb="get",
            api_url=dict(),
            req_args=dict(),
            data=dict(
                ok=True, members=["pollo"], response_metadata=dict(next_cursor="")
            ),
            headers=dict(),
            status_code=200,
        ),
    ]
    # mocker.patch("member_card.slack.WebClient").return_value = mock_client
    # with app.app_context():
    # in app context cause method being called depends on some implicit current_app.config bits...
    assert (
        len(
            list(
                slack.slack_members_generator(
                    client=mock_client,
                    chunk_size=test_chunk_size,
                    polling_interval_secs=0,
                )
            )
        )
        == 3
    )

    # assert return_value is not None
    mock_client.users_list.assert_called_with(
        limit=test_chunk_size, cursor=test_next_cursor
    )


def test_slack_members_etl(app: "Flask", mocker: "MockerFixture"):
    mock_client = mocker.create_autospec(WebClient, instance=True)
    mock_slack_members_generator = mocker.patch(
        "member_card.slack.slack_members_generator"
    )
    mock_slack_members_generator.return_value = [
        {
            "id": "W012A3CDE",
            "team_id": "T012AB3C4",
            "name": "gracky",
            "deleted": False,
            "color": "9f69e7",
            "real_name": "gracky",
            "tz": "America/Los_Angeles",
            "tz_label": "Pacific Daylight Time",
            "tz_offset": -25200,
            "profile": {
                "avatar_hash": "ge3b51ca72de",
                "status_text": "Print is dead",
                "status_emoji": ":books:",
                "real_name": "Egon Gracky",
                "display_name": "gracky",
                "real_name_normalized": "Egon Gracky",
                "display_name_normalized": "gracky",
                "email": "gracky@ghostbusters.example.com",
                "image_24": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                "image_32": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                "image_48": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                "image_72": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                "image_192": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                "image_512": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                "team": "T012AB3C4",
            },
            "is_admin": True,
            "is_owner": False,
            "is_primary_owner": False,
            "is_restricted": False,
            "is_ultra_restricted": False,
            "is_bot": False,
            "updated": 1502138686,
            "is_app_user": False,
            "has_2fa": False,
        },
        {
            "id": "W07QCRPA4",
            "team_id": "T0G9PQBBK",
            "name": "glinda",
            "deleted": False,
            "color": "9f69e7",
            "real_name": "Glinda Southgood",
            "tz": "America/Los_Angeles",
            "tz_label": "Pacific Daylight Time",
            "tz_offset": -25200,
            "profile": {
                "avatar_hash": "8fbdd10b41c6",
                "image_24": "https://a.slack-edge.com...png",
                "image_32": "https://a.slack-edge.com...png",
                "image_48": "https://a.slack-edge.com...png",
                "image_72": "https://a.slack-edge.com...png",
                "image_192": "https://a.slack-edge.com...png",
                "image_512": "https://a.slack-edge.com...png",
                "image_1024": "https://a.slack-edge.com...png",
                "image_original": "https://a.slack-edge.com...png",
                "first_name": "Glinda",
                "last_name": "Southgood",
                "title": "Glinda the Good",
                "phone": "",
                "skype": "",
                "real_name": "Glinda Southgood",
                "real_name_normalized": "Glinda Southgood",
                "display_name": "Glinda the Fairly Good",
                "display_name_normalized": "Glinda the Fairly Good",
                "email": "glenda@south.oz.coven",
            },
            "is_admin": True,
            "is_owner": False,
            "is_primary_owner": False,
            "is_restricted": False,
            "is_ultra_restricted": False,
            "is_bot": False,
            "updated": 1480527098,
            "has_2fa": False,
        },
    ]
    with app.app_context():
        # in app context cause method being called depends on some implicit current_app.config bits...
        assert slack.slack_members_etl(client=mock_client)

    # assert return_value is not None
    # mock_client.users_list.assert_called_with(
    #     limit=test_chunk_size, cursor=test_next_cursor
    # )


# def test_update_sendgrid_template(app: "Flask", mocker: "MockerFixture"):
#     template_id = "test-template-id"
#     test_template_version = dict(
#         id="test-version-id",
#         html_content="<hi></hi>",
#         plain_content="HI! :)",
#         editor="cats-editor",
#     )
#     test_template = {
#         "versions": [test_template_version],
#     }
#     app.config["SENDGRID_TEMPLATE_ID"] = template_id
#     # mock_sg_client = mocker.create_autospec(BaseInterface, instance=True)
#     # mocker.patch("member_card.sendgrid.SendGridAPIClient").return_value = mock_sg_client
#     mock_sg_class = mocker.patch("member_card.sendgrid.SendGridAPIClient")
#     mock_sg = mock_sg_class.return_value

#     mock_template_req = mock_sg.client.templates._.return_value

#     mock_template_get = mock_template_req.get.return_value
#     mock_template_get.body.decode.return_value = json.dumps(test_template)

#     # mock_template_req.versions._().patch.return_value = json.dumps(test_patch_resp)

#     with app.app_context():
#         # in app context cause method being called depends on some implicit current_app.config bits...
#         return_value = sendgrid.update_sendgrid_template()

#     assert return_value is not None
#     assert mock_sg_class.call_args_list
