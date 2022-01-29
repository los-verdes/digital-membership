from uuid import UUID

from flask import g, jsonify, request, send_file

# from logzero import logger
import logging
from member_card import app
from member_card.db import db
from member_card.models import AppleDeviceRegistration, MembershipCard


@app.route("/passkit/v1/log", methods=["POST"])
def passkit_log():
    logging.debug(f"passkit_log() => {request.headers=}")
    logging.debug(f"passkit_log() => {request.get_data()=}")
    logging.warning(f"passkit_log() => {request.get_json()=}")
    return "thanks!"


@app.route("/passkit/v1/passes/<pass_type_identifier>/<serial_number>")
def show(pass_type_identifier, serial_number):
    """
    Getting the latest version of a MembershipCard
    Keyword arguments:
    pass_type_identifier -- The pass’s type, as specified in the pass
    serial_number -- The unique pass identifier, as specified in the pass
    """
    logging.debug(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('ApplePass', 'EMPTY!')[-4:]=}"
    )
    logging.debug(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('Authorization', 'EMPTY!')[-4:]=}"
    )
    logging.debug(
        f"passkit::show() => {list(request.headers.keys())=} ==> {request.headers.get('if-modified-since', 'EMPTY!')[-4:]=}"
    )
    # We store a card's serial number as a UUID in our database, but represent it as a
    # 128-bit integer for our apple passes
    serial_number = UUID(int=serial_number)

    p = MembershipCard.query.filter(
        apple_pass_type_identifier=pass_type_identifier,
        serial_number=serial_number,
    )
    if p:

        from member_card.passes import get_apple_pass_for_user

        current_user = g.user
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
    # return jsonify(p.data)
    return "", 304


@app.route(
    "/passkit/v1/devices/<device_library_identifier>/registrations/<pass_type_identifier>"
)
def index(device_library_identifier, pass_type_identifier):
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
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier
    ).first_or_404()

    r = p.registrations.filter_by(device_library_identifier=device_library_identifier)
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


@app.route(
    "/passkit/v1/devices/<device_library_identifier>/registrations/<pass_type_identifier>/<serial_number>",
    methods=["POST"],
)
def create(device_library_identifier, pass_type_identifier, serial_number):
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
    serial_number = UUID(int=serial_number)
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier, serial_number=serial_number
    ).first_or_404()

    registrations = p.registrations.filter_by(
        device_library_identifier=device_library_identifier
    )
    registrations.push_token = request.form["push_token"]

    db.session.add(registrations)
    db.session.commit()

    return ("Created", 201)


@app.route(
    "/passkit/v1/devices/<device_library_identifier>/registrations/<pass_type_identifier>/<serial_number>",
    methods=["DELETE"],
)
def destroy(device_library_identifier, pass_type_identifier, serial_number):
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
    serial_number = UUID(int=serial_number)
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier,
        serial_number=serial_number,
    ).first_or_404()
    registrations = p.registrations.filter_by(
        device_library_identifier=device_library_identifier
    ).first_or_404()

    db.session.delete(registrations)
    db.session.commit()

    return ("OK", 200)
