import logging
import re
from datetime import datetime, timezone
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
        supported_auth_header_schemes = [
            "ApplePass",
        ]
        logger.debug(
            f"{f.__name__} => {list(request.headers.keys())=} ==> {request.headers.get('Authorization', 'EMPTY!')[-4:]=}"
        )
        logger.debug(
            f"{f.__name__} ==> {request.headers.get('If-Modified-Since', 'EMPTY!')=}"
        )

        pass_type_identifier = kwargs["pass_type_identifier"]
        serial_number = kwargs["serial_number"]

        # We store a card's serial number as a UUID in our database, but represent it as a
        # 128-bit integer for our apple passes
        serial_number = UUID(int=int(serial_number))
        auth_header = request.headers.get("Authorization")
        auth_header_scheme, incoming_token = auth_header.split(" ", 1)
        assert (
            auth_header_scheme in supported_auth_header_schemes
        ), f"{auth_header_scheme=} not in {supported_auth_header_schemes=}"
        log_extra = dict(
            pass_type_identifier=pass_type_identifier,
            serial_number=str(serial_number),
            # TODO: drop this soonish
            auth_header=auth_header,
            incoming_token=incoming_token,
        )

        # See if we can find the relevant card:
        logger.debug(
            f"Looking up card for Apple pass {serial_number=}", extra=log_extra
        )
        p = MembershipCard.query.filter_by(
            apple_pass_type_identifier=pass_type_identifier, serial_number=serial_number
        ).first_or_404()

        log_extra.update(dict(card=p))

        # Then return a 401 unless the signed auth token from the request Auth header matches the indicated card:
        logger.debug(f"Verifying token for {p=}", extra=log_extra)
        token_verified = verify(
            signature=incoming_token, data=p.authentication_token_hex
        )
        if not token_verified:
            logger.warning(f"Unable to verify token for {p=}", extra=log_extra)
            return "unable to verify auth token", 401
        logger.debug(f"Token verified for {p=}!", extra=log_extra)
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
    log_extra = dict(
        device_library_identifier=device_library_identifier,
        membership_card_pass=str(membership_card_pass),
        serial_number=str(membership_card_pass.serial_number),
    )
    logger.info(
        f"registering passkit {device_library_identifier=} for {membership_card_pass=}",
        extra=log_extra,
    )
    push_token = request.form["pushToken"]
    # Next, see if we _already_ have a registration for this device
    logger.debug(
        f"Grabbed {push_token=}, looking up any existing registrations...",
        extra=log_extra,
    )

    registration = membership_card_pass.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier, push_token=push_token
    ).first()
    if registration:
        logger.warning(
            f"passkit {device_library_identifier=} / {membership_card_pass=} already registered!: {registration=}",
            extra=log_extra,
        )
        return "already registered!", 200

    # Finally, create the registration if we have made it this far:
    logger.info(
        f"creating new device registration for {device_library_identifier=} / {membership_card_pass=}",
        extra=log_extra,
    )
    registration = get_or_create(
        session=db.session,
        model=AppleDeviceRegistration,
        membership_card_id=membership_card_pass.id,
        device_library_identifier=device_library_identifier,
    )
    log_extra.update(dict(registration=registration))
    registration.push_token = push_token

    logger.info(
        f"Saving new device registration for {device_library_identifier=} / {membership_card_pass=}",
        extra=log_extra,
    )
    db.session.add(registration)
    db.session.commit()

    logger.info(
        f"passkit {device_library_identifier=} / {membership_card_pass=} registration created!: {registration=}",
        extra=log_extra,
    )
    logger.info(
        "passkit_register_device_for_pass_push_notifications() request",
        extra=log_extra,
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
    log_extra = dict(
        device_library_identifier=device_library_identifier,
        pass_type_identifier=pass_type_identifier,
    )
    logger.debug(
        f"getting serial numbers for {device_library_identifier=} ({pass_type_identifier=})",
        extra=log_extra,
    )
    p = MembershipCard.query.filter_by(
        apple_pass_type_identifier=pass_type_identifier
    ).first_or_404()
    log_extra.update(dict(serial_number=str(p.serial_number)))
    logger.debug(
        f"found {p=} for {device_library_identifier=} ({pass_type_identifier=})",
        extra=log_extra,
    )
    r = p.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier
    )
    logger.debug(
        f"found registration {r=} ({p=}) for {device_library_identifier=} ({pass_type_identifier=})",
        extra=log_extra,
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
        last_last_updated = datetime.utcnow().replace(tzinfo=timezone.utc)
        logger.debug(
            f"Updating existing device registration for {device_library_identifier} from {r.last_updated=} => {last_last_updated=}",
            extra=log_extra,
        )
        r.last_updated = last_last_updated
        db.session.add(r)
        db.session.commit()
        logger.info(
            f"{r=} ({p=}) being returned for {device_library_identifier=} ({pass_type_identifier=}): {response=}",
            extra=log_extra,
        )
        return response

    else:
        logger.info(
            f"no {r=} ({p=}) left to return for {device_library_identifier=} ({pass_type_identifier=})!",
            extra=log_extra,
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
    log_extra = dict(
        device_library_identifier=device_library_identifier,
        membership_card_pass=str(membership_card_pass),
        serial_number=str(membership_card_pass.serial_number),
    )
    if modified_since_header := request.headers.get("If-Modified-Since"):
        logger.debug(f"parsing modified since header: {modified_since_header}")
        if_modified_since = parse(modified_since_header).replace(tzinfo=timezone.utc)
        logger.debug(
            f"filtering {membership_card_pass=} ({membership_card_pass.time_updated=}) with {if_modified_since=}",
            extra=log_extra,
        )
        if membership_card_pass.time_updated <= if_modified_since:
            logger.debug(
                f"{membership_card_pass=}'s {membership_card_pass.time_updated=} ({device_library_identifier=}) >= {if_modified_since=}",
                extra=log_extra,
            )
            return "not modified since", 304

    logger.debug(f"found in {membership_card_pass=} ({device_library_identifier=}).")

    from member_card.passes import get_apple_pass_for_user

    attachment_filename = (
        f"lv_apple_pass-{membership_card_pass.user.last_name.lower()}.pkpass"
    )
    logger.info(
        f"generating updated pass for {membership_card_pass.user=}",
        extra=log_extra,
    )
    pkpass_out_path = get_apple_pass_for_user(
        user=membership_card_pass.user,
    )
    logger.info(
        f"sending out updated pass with {attachment_filename=}",
        extra=log_extra,
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
    log_extra = dict(
        device_library_identifier=device_library_identifier,
        membership_card_pass=str(membership_card_pass),
        serial_number=str(membership_card_pass.serial_number),
    )
    registrations = membership_card_pass.apple_device_registrations.filter_by(
        device_library_identifier=device_library_identifier
    ).all()
    if not registrations:
        logger.debug(
            f"no {registrations=} found for {device_library_identifier=} ({membership_card_pass=})",
            extra=log_extra,
        )
        # TODO: remove this once we done iterating on passkit webserver implementation?
        logger.warning(
            "ignoring missing registrations for now...",
            extra=log_extra,
        )
        return ("OK", 200)
        # return ("NO REGISTRATION FOUND", 404)

    logger.debug(
        f"found {registrations=} for {device_library_identifier=} ({membership_card_pass=})",
        extra=log_extra,
    )
    db.session.delete(registrations)
    db.session.commit()
    return ("OK", 200)


PASSKIT_LOG_REGEXPS = [
    re.compile(
        r"\[(?P<datetime_str>[0-9]{4}-[0-9]{2}-[0-9]{2}.*)\] (?P<task_name>[^(]+) \(for device (?P<device_id>[^,]+), pass type (?P<pass_type>[^,]+), serial number (?P<serial_num>[0-9]+); with web service url (?P<service_url>[^)]+)\) encountered error: (?P<error_msg>.*)"
    ),
    re.compile(
        r"\[(?P<datetime_str>[0-9]{4}-[0-9]{2}-[0-9]{2}.*)\] (?P<task_name>[^(]+) \(pass type (?P<pass_type>[^,]+), serial number (?P<serial_num>[0-9]+), if-modified-since (?P<if_modified_since>[^;]+); with web service url (?P<service_url>[^)]+)\) encountered error: (?P<error_msg>.*)"
    ),
]


@app.route("/passkit/v1/log", methods=["POST"])
def passkit_error_log():
    # TODO: parse these out so we can filter better using log `extra`:
    # 1. "passkit_log() => request.get_json()={'logs': ['[2022-02-10 12:49:07 -0600]
    #   Register task (for device 67cdbaff6b4fddc7df72e25e63d033f6, pass type pass.es.losverd.card, serial number 309215912519139528122129481752503817974;
    #   with web service url https://card.losverd.es/passkit) encountered error: Authentication failure']}"
    # 2. {'logs': ['[2022-02-10 12:44:07 -0600] Get pass task (pass type pass.es.losverd.card, serial number 44396170818453607218698234240486608995,
    #   if-modified-since (null); with web service url https://card.losverd.es/passkit) encountered error: Authentication failure']}"
    # 3. [2022-02-10 12:34:16 -0600] Unregister task (for device 7c0cd34b7bcac27893ab2e576a0dbd2c, pass type pass.es.losverd.card, serial number 122890994920237774731868014825964879062; with web service url https://card.losverd.es/passkit) encountered error: Authentication failure
    parsed_log_entries = []
    raw_log_entries = request.get_json().get("logs", [])
    for raw_log_entry in raw_log_entries:
        for regexp in PASSKIT_LOG_REGEXPS:
            if matches := regexp.match(raw_log_entry):
                parsed_log_entries.append(matches.groupdict())
                break
        else:
            parsed_log_entries.append(raw_log_entry)

    logger.warning(
        f"passkit_log() => {request.get_json()=}",
        extra=dict(
            parsed_log_entries=parsed_log_entries, raw_log_entries=raw_log_entries
        ),
    )
    return "thanks!"
