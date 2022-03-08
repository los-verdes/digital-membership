from member_card.models import SquarespaceWebhook


def test_to_dict():
    webhook = SquarespaceWebhook()
    assert isinstance(webhook.to_dict(), dict)
