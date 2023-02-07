from member_card.models import AppleDeviceRegistration


def test_repr():
    registration = AppleDeviceRegistration()
    assert repr(registration).startswith("<AppleDeviceRegistration")
