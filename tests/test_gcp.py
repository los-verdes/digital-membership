import json
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1
from member_card import gcp

if TYPE_CHECKING:
    from flask import Flask
    from pytest_mock.plugin import MockerFixture


def test_publish_message(mocker: "MockerFixture"):
    mock_futures = mocker.patch("member_card.gcp.futures")

    mock_publisher = mocker.create_autospec(pubsub_v1.PublisherClient)
    mocker.patch(
        "member_card.gcp.pubsub_v1"
    ).PublisherClient.return_value = mock_publisher

    test_topic_path = "test-topic-path"
    mock_publisher.topic_path.return_value = test_topic_path

    test_project_id = "test-project"
    test_topic_id = "test-topic"
    test_message_data = {"this-is": "a-test"}

    gcp.publish_message(
        project_id=test_project_id,
        topic_id=test_topic_id,
        message_data=test_message_data,
    )

    mock_publisher.publish.assert_called_once_with(
        test_topic_path, json.dumps(test_message_data).encode("utf-8")
    )

    mock_futures.stop()
    mock_futures.wait.assert_called_once_with(
        [mock_publisher.publish.return_value], return_when=mock_futures.ALL_COMPLETED
    )


def test_retrieve_app_secrets(mocker: "MockerFixture"):
    mock_secrets_client_class = mocker.patch(
        "member_card.gcp.SecretManagerServiceClient"
    )
    mock_secrets_client = mock_secrets_client_class.return_value

    test_secret_name = "test-secret-name"
    test_secret = dict(this_is="a-secret")
    mock_response = mock_secrets_client.access_secret_version.return_value
    mock_response.payload.data.decode.return_value = json.dumps(test_secret)

    result = gcp.retrieve_app_secrets(secret_name=test_secret_name)

    assert result == test_secret

    mock_secrets_client.access_secret_version.assert_called_once_with(
        request=dict(name=test_secret_name)
    )


def test_retrieve_app_secrets_none_secret_name():
    result = gcp.retrieve_app_secrets(secret_name=None)

    assert result == gcp.DEFAULT_SECRET_PLACEHOLDERS


def test_get_gcs_client(mocker: "MockerFixture"):
    mock_storage = mocker.patch("member_card.gcp.storage")
    gcp.get_gcs_client()
    mock_storage.Client.assert_called_once()


def test_get_bucket_implicit_client(app: "Flask", mocker: "MockerFixture"):
    mock_client = mocker.Mock()
    mock_get_client = mocker.patch("member_card.gcp.get_gcs_client")
    mock_get_client.return_value = mock_client
    with app.app_context():
        # in app context cause method being called depends on some implicit current_app.config bits...
        gcp.get_bucket()
    mock_get_client.assert_called_once()
    mock_client.get_bucket.assert_called_once()


def test_get_bucket_explicit_client(app: "Flask", mocker: "MockerFixture"):
    mock_client = mocker.Mock()
    mock_get_client = mocker.patch("member_card.gcp.get_gcs_client")
    mock_get_client.return_value = mock_client
    with app.app_context():
        # in app context cause method being called depends on some implicit current_app.config bits...
        gcp.get_bucket(client=mock_client)
    mock_get_client.assert_not_called()
    mock_client.get_bucket.assert_called_once()


def test_upload_file_to_gcs(app: "Flask", mocker: "MockerFixture"):
    mock_blob = mocker.Mock()
    mock_bucket = mocker.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_get_bucket = mocker.patch("member_card.gcp.get_bucket")
    mock_get_bucket.return_value = mock_bucket
    local_file = "test-local-file"
    remote_path = "test-remote-path"

    with app.app_context():
        # in app context cause method being called depends on some implicit current_app.config bits...
        gcp.upload_file_to_gcs(
            bucket=mock_bucket,
            local_file=local_file,
            remote_path=remote_path,
            content_type="x-some-type",
        )

    mock_bucket.blob.assert_called_with(remote_path)
    mock_blob.upload_from_filename.assert_called_with(local_file)
