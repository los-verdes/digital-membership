from typing import TYPE_CHECKING
from datetime import datetime
from member_card.db import db
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


def test_latest_membership_card_yes_active_membership(app: "Flask", fake_card: "MembershipCard"):
    with app.app_context():
        card = db.session.merge(fake_card)
        assert card.user.latest_membership_card


def test_edit_user_name_success(app: "Flask", fake_user: "User"):
    new_first_name = "You done"
    new_last_name = "Been Edited"
    new_fullname = f"{new_first_name} {new_last_name}"
    with app.app_context():
        edit_user_name(
            user=fake_user,
            new_first_name=new_first_name,
            new_last_name=new_last_name,
        )
        updated_fake_user = User.query.filter_by(id=fake_user.id).one()
    assert updated_fake_user.first_name == new_first_name
    assert updated_fake_user.last_name == new_last_name
    assert updated_fake_user.fullname == new_fullname


def test_ensure_user_is_idempotent(app: "Flask", fake_user: "User"):
    with app.app_context():
        user = ensure_user(
            email=fake_user.email,
            first_name=fake_user.first_name,
            last_name=fake_user.last_name,
        )
        user_id = user.id
    assert user_id == fake_user.id


def test_ensure_user_sets_empty_fullname(app: "Flask", fake_user: "User"):
    with app.app_context():
        user = ensure_user(
            email=fake_user.email,
            first_name=fake_user.first_name,
            last_name=fake_user.last_name,
        )
        fullname = user.fullname
    assert fullname


def test_ensure_user_different_first_name(app: "Flask", fake_user: "User"):
    with app.app_context():
        user = ensure_user(
            email=fake_user.email,
            first_name="a-different-one",
            last_name=fake_user.last_name,
        )
        first_name = user.first_name
    assert first_name == fake_user.first_name


def test_ensure_user_different_last_name(app: "Flask", fake_user: "User"):
    with app.app_context():
        user = ensure_user(
            email=fake_user.email,
            first_name=fake_user.first_name,
            last_name="a-different-one",
        )
        last_name = user.last_name
    assert last_name == fake_user.last_name


def test_ensure_user_sets_username(app: "Flask", fake_user: "User"):
    with app.app_context():
        user = ensure_user(
            email=fake_user.email,
            first_name=fake_user.first_name,
            last_name=fake_user.last_name,
            username="new-username?",
        )
        username = user.username
    assert username


def test_ensure_user_sets_password(app: "Flask", fake_user: "User"):
    with app.app_context():
        user = ensure_user(
            email=fake_user.email,
            first_name=fake_user.first_name,
            last_name=fake_user.last_name,
            password="new-password?",
        )
        password = user.password
    assert password
