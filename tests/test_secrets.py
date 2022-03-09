from typing import TYPE_CHECKING
import json
from member_card import secrets

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


def test_retrieve_app_secrets(mocker: "MockerFixture"):
    mock_secrets_client_class = mocker.patch(
        "member_card.secrets.SecretManagerServiceClient"
    )
    mock_secrets_client = mock_secrets_client_class.return_value

    test_secret_name = "test-secret-name"
    test_secret = dict(this_is="a-secret")
    mock_response = mock_secrets_client.access_secret_version.return_value
    mock_response.payload.data.decode.return_value = json.dumps(test_secret)

    result = secrets.retrieve_app_secrets(secret_name=test_secret_name)

    assert result == test_secret

    mock_secrets_client.access_secret_version.assert_called_once_with(
        request=dict(name=test_secret_name)
    )


def test_retrieve_app_secrets_none_secret_name():
    result = secrets.retrieve_app_secrets(secret_name=None)

    assert result == secrets.DEFAULT_SECRET_PLACEHOLDERS
