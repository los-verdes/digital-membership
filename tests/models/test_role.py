from member_card.models import Role


def test_str():
    role = Role()
    assert str(role).startswith("<Role")


def test_repr():
    role = Role()
    assert repr(role).startswith("<Role")
