import logging
from datetime import timezone
from functools import wraps
from uuid import UUID

from dateutil.parser import parse
from flask import jsonify, request, send_file
from member_card.app import app
from member_card.db import db, get_or_create
from member_card.models import AppleDeviceRegistration, MembershipCard
from member_card.utils import verify

logger = logging.getLogger(__name__)


def applepass_auth_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.info(
            f"{f.__name__} => {list(request.headers.keys())=} ==> {request.headers.get('Authorization', 'EMPTY!')[-4:]=}"
        )
        logger.info(
            f"{f.__name__} ==> {request.headers.get('If-Modified-Since', 'EMPTY!')=}"
        )

        pass_type_identifier = kwargs["pass_type_identifier"]
        serial_number = kwargs["serial_number"]

        # We store a card's serial number as a UUID in our database, but represent it as a
        # 128-bit integer for our apple passes
        serial_number = UUID(int=int(serial_number))
        auth_header = request.headers.get("Authorization")
        incoming_token = auth_header.lstrip("ApplePass ")

        # See if we can find the relevant card:
        p = MembershipCard.query.filter_by(
            apple_pass_type_identifier=pass_type_identifier, serial_number=serial_number
        ).first_or_404()

        # Then return a 401 unless the signed auth token from the request Auth header matches the indicated card:
        token_verified = incoming_token == p.authentication_token_hex
        if not token_verified:
            return "unable to verify auth token", 401

        return f(
            *args,
            membership_card_pass=p,
            device_library_identifier=kwargs.get("device_library_identifier"),
        )

    return decorated_function


@app.route(
    "/passkit/v1/devices/<device_library_identifier>/registrations/<pass_type_identifier>/<serial_number>",
    methods=["POST"],
)
@applepass_auth_token_required
def passkit_register_device_for_pass_push_notifications(
    membership_card_pass, device_library_identifier
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
    push_token = request.form["pushToken"]
    # Next, see if we _already_ have a registration for this device
    logger.info(
        f"registering passkit {device_library_identifier=} for {membership_card_pass=}"
    )
    registration = membership_card_pass.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier, push_token=push_token
    ).first()
    if registration:
        logger.info(
            f"passkit {device_library_identifier=} / {membership_card_pass=} already registered!: {registration=}"
        )
        return "already registered!", 200

    # Finally, create the registration if we have made it this far:
    logger.info(
        f"creating new device registration for {device_library_identifier=} / {membership_card_pass=}"
    )
    registration = get_or_create(
        session=db.session,
        model=AppleDeviceRegistration,
        membership_card_id=membership_card_pass.id,
        device_library_identifier=device_library_identifier,
    )
    registration.push_token = push_token
    db.session.add(registration)
    db.session.commit()

    logger.info(
        f"passkit {device_library_identifier=} / {membership_card_pass=} registration created!: {registration=}"
    )
    logger.info(
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
    logger.debug(
        f"getting serial numbers for {device_library_identifier=} ({pass_type_identifier=})"
    )
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier
    ).first_or_404()
    logger.debug(
        f"found {p=} for {device_library_identifier=} ({pass_type_identifier=})"
    )
    r = p.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier
    )
    logger.debug(
        f"found registration {r=} ({p=}) for {device_library_identifier=} ({pass_type_identifier=})"
    )
    if "passesUpdatedSince" in request.args:
        passes_updated_since = request.args["passesUpdatedSince"]
        logger.debug(f"filtering registration {r=} ({p=}) with {passes_updated_since=}")
        r = r.filter(AppleDeviceRegistration.time_updated >= passes_updated_since)
        logger.debug(
            f"after filtering registration with {passes_updated_since=}: {r=} ({p=}) "
        )

    if r:
        # XXX: Is this the correct return value for serial number?
        response = jsonify(
            {
                "lastUpdated": p.time_updated,
                "serialNumbers": [p.apple_pass_serial_number],
            }
        )
        logger.debug(
            f"{r=} ({p=}) being returned for {device_library_identifier=} ({pass_type_identifier=}): {response=}"
        )
        return response

    else:
        logger.debug(
            f"no {r=} ({p=}) left to return for {device_library_identifier=} ({pass_type_identifier=})!"
        )
        return ("No Content", 204)


@app.route("/passkit/v1/passes/<pass_type_identifier>/<serial_number>")
@applepass_auth_token_required
def passkit_get_latest_version_of_pass(membership_card_pass, device_library_identifier):
    """
    Getting the latest version of a MembershipCard
    Keyword arguments:
    pass_type_identifier -- The pass’s type, as specified in the pass
    serial_number -- The unique pass identifier, as specified in the pass
    """

    if modified_since_header := request.headers.get("If-Modified-Since"):
        logger.debug(f"parsing modified since header: {modified_since_header}")
        if_modified_since = parse(modified_since_header).replace(tzinfo=timezone.utc)
        logger.debug(
            f"filtering {membership_card_pass=} ({membership_card_pass.time_updated=}) with {if_modified_since=}"
        )
        if membership_card_pass.time_updated <= if_modified_since:
            logger.debug(
                f"{membership_card_pass=}'s {membership_card_pass.time_updated=} ({device_library_identifier=}) >= {if_modified_since=}"
            )
            return "not modified since", 304

    logger.debug(f"found in {membership_card_pass=} ({device_library_identifier=}).")

    from member_card.passes import get_apple_pass_for_user

    attachment_filename = (
        f"lv_apple_pass-{membership_card_pass.user.last_name.lower()}.pkpass"
    )
    logger.info(f"generating updated pass for {membership_card_pass.user=}")
    pkpass_out_path = get_apple_pass_for_user(
        user=membership_card_pass.user,
    )
    logger.info(f"sending out updated pass with {attachment_filename=}")
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
@applepass_auth_token_required
def passkit_unregister_a_device(membership_card_pass, device_library_identifier):
    """
    Unregistering a device
    Keyword arguments:
    device_library_identifier -- A unique identifier that is used to identify
                                 and authenticate the device
    pass_type_identifier      -- The pass’s type, as specified in the pass
    serial_number             -- The unique pass identifier, as specified in
                                 the pass
    """
    registrations = membership_card_pass.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier
    ).all()
    if not registrations:
        logger.debug(
            f"no {registrations=} found for {device_library_identifier=} ({membership_card_pass=})"
        )
        # TODO: remove this once we done iterating on passkit webserver implementation?
        logger.warning("ignoring missing registrations for now...")
        return ("OK", 200)
        # return ("NO REGISTRATION FOUND", 404)

    logger.debug(
        f"found {registrations=} for {device_library_identifier=} ({membership_card_pass=})"
    )
    db.session.delete(registrations)
    db.session.commit()
    return ("OK", 200)


@app.route("/passkit/v1/log", methods=["POST"])
def passkit_error_log():
    logger.debug(f"passkit_log() => {request.headers=}")
    logger.debug(f"passkit_log() => {request.get_data()=}")
    logger.warning(f"passkit_log() => {request.get_json()=}")
    return "thanks!"
