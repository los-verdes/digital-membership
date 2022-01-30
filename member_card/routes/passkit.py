import logging
from uuid import UUID

from flask import jsonify, request, send_file
from member_card import app
from member_card.db import db, get_or_create
from member_card.models import AppleDeviceRegistration, MembershipCard
from member_card.utils import verify

# from functools import wraps

# from flask import g, request, redirect, url_for

# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if g.user is None:
#             return redirect(url_for('login', next=request.url))
#         return f(*args, **kwargs)
#     return decorated_function


def verify_applepass_auth_token_header(auth_header, card_authentication_token_hex):
    incoming_token = auth_header.lstrip("ApplePass ")

    token_verified = verify(
        signature=incoming_token, data=card_authentication_token_hex
    )
    return token_verified


@app.route(
    "/passkit/v1/devices/<device_library_identifier>/registrations/<pass_type_identifier>/<serial_number>",
    methods=["POST"],
)
def passkit_register_device_for_pass_push_notifications(
    device_library_identifier, pass_type_identifier, serial_number
):
    """
    Registering a device to receive push notifications for a pass
    Keyword arguments:
    device_library_identifier -- A unique identifier that is used to identify
                                 and authenticate the device
    pass_type_identifier      -- The pass’s type, as specified in the pass
    serial_number             -- The unique pass identifier, as specified in
                                 the pass
    """
    logging.info(
        f"passkit::create() => {list(request.headers.keys())=} ==> {request.headers.get('ApplePass', 'EMPTY!')[-4:]=}"
    )
    logging.info(
        f"passkit::create() => {list(request.headers.keys())=} ==> {request.headers.get('Authorization', 'EMPTY!')[-4:]=}"
    )

    # We store a card's serial number as a UUID in our database, but represent it as a
    # 128-bit integer for our apple passes
    serial_number = UUID(int=int(serial_number))
    auth_header = request.headers.get("Authorization")
    push_token = request.form["pushToken"]

    # See if we can find the relevant card:
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier, serial_number=serial_number
    ).first_or_404()

    # Then return a 401 unless the signed auth token from the request Auth header matches the indicated card:
    token_verified = verify_applepass_auth_token_header(
        auth_header=auth_header,
        card_authentication_token_hex=p.authentication_token_hex,
    )
    if not token_verified:
        return "unable to verify auth token", 401

    # Next, see if we _already_ have a registration for this device
    registration = p.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier, push_token=push_token
    ).first()
    if registration:
        return "already registered!", 200

    # Finally, create the registration if we have made it this far:
    registration = get_or_create(
        session=db.session,
        model=AppleDeviceRegistration,
        membership_card_id=p.id,
        device_library_identifier=device_library_identifier,
    )
    registration.push_token = push_token
    db.session.add(registration)
    db.session.commit()

    logging.info(
        "passkit_register_device_for_pass_push_notifications() request",
        extra=dict(registration=registration),
    )
    return ("created", 201)


@app.route(
    "/passkit/v1/devices/<device_library_identifier>/registrations/<pass_type_identifier>"
)
def get_serial_numbers_for_device_passes(
    device_library_identifier, pass_type_identifier
):
    """
    Getting the serial numbers for passes associated with a device
    Keyword arguments:
    device_library_identifier -- A unique identifier that is used to identify
                                 and authenticate the device
    pass_type_identifier      -- The pass’s type, as specified in the pass
    If the passes_updated_since parameter is present, return only the passes
    that have been updated since the time indicated by tag. Otherwise, return
    all passes.
    """
    logging.info(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('ApplePass', 'EMPTY!')[-4:]=}"
    )
    logging.info(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('Authorization', 'EMPTY!')[-4:]=}"
    )
    auth_header = request.headers.get("Authorization")
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier
    ).first_or_404()

    # Then return a 401 unless the signed auth token from the request Auth header matches the indicated card:
    token_verified = verify_applepass_auth_token_header(
        auth_header=auth_header,
        card_authentication_token_hex=p.authentication_token_hex,
    )
    if not token_verified:
        return "unable to verify auth token", 401

    r = p.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier
    )
    if "passesUpdatedSince" in request.args:
        r = r.filter(
            AppleDeviceRegistration.time_updated >= request.args["passesUpdatedSince"]
        )

    if r:
        # XXX: Is this the correct return value for serial number?
        return jsonify(
            {
                "lastUpdated": p.time_updated,
                "serialNumbers": [p.apple_pass_serial_number],
            }
        )
    else:
        return ("No Content", 204)


@app.route("/passkit/v1/passes/<pass_type_identifier>/<serial_number>")
def passkit_get_latest_version_of_pass(pass_type_identifier, serial_number):
    """
    Getting the latest version of a MembershipCard
    Keyword arguments:
    pass_type_identifier -- The pass’s type, as specified in the pass
    serial_number -- The unique pass identifier, as specified in the pass
    """
    logging.info(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('ApplePass', 'EMPTY!')[-4:]=}"
    )
    logging.info(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('Authorization', 'EMPTY!')[-4:]=}"
    )
    logging.info(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('If-Modified-Since', 'EMPTY!')[-4:]=}"
    )
    # We store a card's serial number as a UUID in our database, but represent it as a
    # 128-bit integer for our apple passes
    serial_number = UUID(int=int(serial_number))
    auth_header = request.headers.get("Authorization")

    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier,
        serial_number=serial_number,
    )

    # Then return a 401 unless the signed auth token from the request Auth header matches the indicated card:
    card = p.first()
    token_verified = verify_applepass_auth_token_header(
        auth_header=auth_header,
        card_authentication_token_hex=card.authentication_token_hex,
    )
    if not token_verified:
        return "unable to verify auth token", 401

    p = p.filter(
        MembershipCard.time_updated >= request.headers.get("If-Modified-Since"),
    ).first()

    if not p:
        return "not modified since", 304
    if p:

        from member_card.passes import get_apple_pass_for_user

        current_user = p.user
        attachment_filename = f"lv_apple_pass-{current_user.last_name.lower()}.pkpass"
        pkpass_out_path = get_apple_pass_for_user(
            user=current_user,
        )
        return send_file(
            pkpass_out_path,
            attachment_filename=attachment_filename,
            mimetype="application/vnd.apple.pkpass",
            as_attachment=True,
        )


@app.route(
    "/passkit/v1/devices/<device_library_identifier>/registrations/<pass_type_identifier>/<serial_number>",
    methods=["DELETE"],
)
def passkit_unregister_a_device(
    device_library_identifier, pass_type_identifier, serial_number
):
    """
    Unregistering a device
    Keyword arguments:
    device_library_identifier -- A unique identifier that is used to identify
                                 and authenticate the device
    pass_type_identifier      -- The pass’s type, as specified in the pass
    serial_number             -- The unique pass identifier, as specified in
                                 the pass
    """
    logging.info(
        f"passkit::destroy() => {list(request.headers.keys())=} ==> {request.headers.get('ApplePass', 'EMPTY!')[-4:]=}"
    )
    logging.info(
        f"passkit::destroy() => {list(request.headers.keys())=} ==> {request.headers.get('Authorization', 'EMPTY!')[-4:]=}"
    )
    # We store a card's serial number as a UUID in our database, but represent it as a
    # 128-bit integer for our apple passes
    serial_number = UUID(int=int(serial_number))
    auth_header = request.headers.get("Authorization")
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier,
        serial_number=serial_number,
    ).first_or_404()

    # Then return a 401 unless the signed auth token from the request Auth header matches the indicated card:
    token_verified = verify_applepass_auth_token_header(
        auth_header=auth_header,
        card_authentication_token_hex=p.authentication_token_hex,
    )
    if not token_verified:
        return "unable to verify auth token", 401
    registrations = p.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier
    ).first_or_404()

    db.session.delete(registrations)
    db.session.commit()

    return ("OK", 200)


@app.route("/passkit/v1/log", methods=["POST"])
def passkit_error_log():
    logging.debug(f"passkit_log() => {request.headers=}")
    logging.debug(f"passkit_log() => {request.get_data()=}")
    logging.warning(f"passkit_log() => {request.get_json()=}")
    return "thanks!"
