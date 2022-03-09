import json
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1
from member_card import pubsub

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


def test_publish_message(mocker: "MockerFixture"):
    mock_futures = mocker.patch("member_card.pubsub.futures")

    mock_publisher = mocker.create_autospec(pubsub_v1.PublisherClient)
    mocker.patch(
        "member_card.pubsub.pubsub_v1"
    ).PublisherClient.return_value = mock_publisher

    test_topic_path = "test-topic-path"
    mock_publisher.topic_path.return_value = test_topic_path

    test_project_id = "test-project"
    test_topic_id = "test-topic"
    test_message_data = {"this-is": "a-test"}

    pubsub.publish_message(
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
