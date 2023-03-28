from member_card.models import Store


def test_repr():
    store = Store(
        store_hash="test_store_hash",
        access_token="test_access_token",
        scope="test_scope",
    )
    store.id = 1
    assert store
    assert repr(store).startswith("<Store id=1")
