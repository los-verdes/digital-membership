from typing import TYPE_CHECKING
from datetime import datetime
from member_card.models import MembershipCard
from member_card.models.user import User, edit_user_name, ensure_user

if TYPE_CHECKING:
    from flask import Flask


def test_str():
    role = User()
    assert str(role).startswith("<User")


def test_to_dict(fake_user: "User"):
    assert isinstance(fake_user.to_dict(), dict)


def test_is_active(fake_user: "User"):
    assert fake_user.is_active()


def test_does_not_has_active_membership(fake_user: "User"):
    assert fake_user.has_active_memberships is False


def test_does_has_active_membership(fake_member: "User"):
    assert fake_member.has_active_memberships


def test_has_memberships_no_memberships(fake_user: "User"):
    assert fake_user.has_memberships() is False


def test_has_memberships_yes_memberships(fake_member: "User"):
    assert fake_member.has_memberships()


def test_member_since_no_active_membership(fake_user: "User"):
    assert fake_user.member_since is None


def test_member_since_yes_active_membership(fake_member: "User"):
    assert isinstance(fake_member.member_since, datetime)


def test_membership_expiry_no_active_membership(fake_user: "User"):
    assert fake_user.membership_expiry is None


def test_membership_expiry_yes_active_membership(fake_member: "User"):
    assert isinstance(fake_member.membership_expiry, datetime)


def test_latest_membership_card_no_active_membership(fake_user: "User"):
    assert fake_user.latest_membership_card is None


def test_latest_membership_card_yes_active_membership(fake_card: "MembershipCard"):
    assert fake_card.user.latest_membership_card


def test_edit_user_name_success(app: "Flask", fake_user: "User"):
    new_first_name = "You done"
    new_last_name = "Been Edited"
    new_fullname = f"{new_first_name} {new_last_name}"
    edit_user_name(
        user=fake_user,
        new_first_name=new_first_name,
        new_last_name=new_last_name,
    )
    with app.app_context():
        updated_fake_user = User.query.filter_by(id=fake_user.id).one()
    assert updated_fake_user.first_name == new_first_name
    assert updated_fake_user.last_name == new_last_name
    assert updated_fake_user.fullname == new_fullname


def test_ensure_user_is_idempotent(fake_user: "User"):
    user = ensure_user(
        email=fake_user.email,
        first_name=fake_user.first_name,
        last_name=fake_user.last_name,
    )
    assert user == fake_user


def test_ensure_user_sets_empty_fullname(fake_user: "User"):
    setattr(fake_user, "fullname", "")
    user = ensure_user(
        email=fake_user.email,
        first_name=fake_user.first_name,
        last_name=fake_user.last_name,
    )
    assert user.fullname


def test_ensure_user_different_first_name(fake_user: "User"):
    user = ensure_user(
        email=fake_user.email,
        first_name="a-different-one",
        last_name=fake_user.last_name,
    )
    assert user.first_name == fake_user.first_name


def test_ensure_user_different_last_name(fake_user: "User"):
    user = ensure_user(
        email=fake_user.email,
        first_name=fake_user.first_name,
        last_name="a-different-one",
    )
    assert user.last_name == fake_user.last_name


def test_ensure_user_sets_username(fake_user: "User"):
    setattr(fake_user, "fullname", "")
    user = ensure_user(
        email=fake_user.email,
        first_name=fake_user.first_name,
        last_name=fake_user.last_name,
        username="new-username?",
    )
    assert user.username


def test_ensure_user_sets_password(fake_user: "User"):
    setattr(fake_user, "fullname", "")
    user = ensure_user(
        email=fake_user.email,
        first_name=fake_user.first_name,
        last_name=fake_user.last_name,
        password="new-password?",
    )
    assert user.password
