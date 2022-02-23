import logging


class TestPubsubIngress:
    def test_get_returns_method_not_allowed(self, client):
        response = client.get("/pubsub")
        logging.debug(f"{response=}")
        # Check that this method is indeed _not_ allowed
        assert response.status_code == 405

    # def test_invalid_message(self, worker_client):
