"""Publishes multiple messages to a Pub/Sub topic with an error handler."""
import json
import logging
from concurrent import futures

from google.cloud import pubsub_v1

logger = logging.getLogger(__name__)


def publish_message(project_id, topic_id, message_data):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    data = json.dumps(message_data).encode("utf-8")
    publish_future = publisher.publish(topic_path, data)

    # Wait for all the publish futures to resolve before exiting.
    futures.wait([publish_future], return_when=futures.ALL_COMPLETED)

    logger.info(f"Published messages with error handler to {topic_path}.")
