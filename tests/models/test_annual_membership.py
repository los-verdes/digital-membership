from datetime import datetime, timezone
from member_card.models import AnnualMembership


def test_to_dict(fake_membership_order: "AnnualMembership"):
    assert isinstance(fake_membership_order.to_dict(), dict)


def test_repr(fake_membership_order: "AnnualMembership"):
    assert repr(fake_membership_order).startswith("<AnnualMembership")


def test_expiry_date_no_created_on():
    membership_order = AnnualMembership()
    assert membership_order.expiry_date is None


class TestIsActive:
    def test_canceled(self):
        membership_order = AnnualMembership()
        membership_order.fulfillment_status = "CANCELED"
        assert membership_order.is_active is False

    # def test_no_created_on(self, fake_membership_order: "AnnualMembership"):
    def test_no_created_on(self):
        membership_order = AnnualMembership()
        membership_order.fulfillment_status = "PENDING"
        assert membership_order.is_active is False

    def test_no_created_on_is_str(self):
        membership_order = AnnualMembership()
        membership_order.fulfillment_status = "PENDING"
        membership_order.created_on = (
            datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
        )
        assert membership_order.is_active is True

    def test_no_created_on_over_year_ago(self):
        membership_order = AnnualMembership()
        membership_order.fulfillment_status = "PENDING"
        membership_order.created_on = AnnualMembership.one_year_ago
        assert membership_order.is_active is False
