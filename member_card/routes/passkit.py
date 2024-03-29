import logging
import re
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
        supported_auth_header_schemes = [
            "ApplePass",
        ]
        logger.debug(
            f"{f.__name__} => entering applepass_auth_token_required() decorator..."
        )

        pass_type_identifier = kwargs["pass_type_identifier"]
        serial_number = kwargs["serial_number"]

        # We store a card's serial number as a UUID in our database, but represent it as a
        # 128-bit integer for our apple passes
        serial_number = UUID(int=int(serial_number))
        auth_header = request.headers.get("Authorization")
        log_extra = dict(
            pass_type_identifier=pass_type_identifier,
            serial_number=str(serial_number),
        )

        if auth_header is None:
            logger.warning("no authorization header in request", extra=log_extra)
            return "unable to verify auth token", 401

        auth_header_scheme, incoming_token = auth_header.split(" ", 1)
        if auth_header_scheme not in supported_auth_header_schemes:
            logger.warning(
                f"{auth_header_scheme} not in {supported_auth_header_schemes}",
                extra=log_extra,
            )
            return f"{auth_header_scheme=} not supported!", 401

        # See if we can find the relevant card:
        logger.debug(
            f"Looking up card for Apple pass {serial_number=}", extra=log_extra
        )
        p = MembershipCard.query.filter_by(
            apple_pass_type_identifier=pass_type_identifier, serial_number=serial_number
        ).first()
        if not p:
            logger.warning(
                f"unable to find membership card matching serial number: {serial_number} ({pass_type_identifier=})",
                extra=log_extra,
            )
            return "unable to find membership card matching serial number", 401

        log_extra.update(dict(card=p, user_email=p.user.email))

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
        request_json=request.json,
        user_email=membership_card_pass.user.email,
    )
    logger.info(
        f"registering passkit {device_library_identifier=} for {membership_card_pass=}",
        extra=log_extra,
    )

    if request.json is None or request.json.get("pushToken") is None:
        logger.warning(
            f"unable to register device for {membership_card_pass=}, no push token provided!"
        )
        return "pushToken required!", 422

    push_token = request.json["pushToken"]

    # Next, see if we _already_ have a registration for this device
    logger.debug(
        f"Grabbed {push_token=}, looking up any existing registrations...",
        extra=log_extra,
    )

    registration = AppleDeviceRegistration.query.filter_by(
        device_library_identifier=device_library_identifier,
        membership_card_id=membership_card_pass.id,
    ).first()

    if registration:
        setattr(registration, "push_token", push_token)
        db.session.add(registration)
        db.session.commit()
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
    registration = AppleDeviceRegistration.query.filter_by(
        device_library_identifier=device_library_identifier
    ).first_or_404()
    membership_cards = [registration.membership_card]
    log_extra.update(dict(registration=registration, membership_cards=membership_cards))
    logger.debug(
        f"found {registration=} for {device_library_identifier=}",
        extra=log_extra,
    )

    passes = membership_cards
    if "passesUpdatedSince" in request.args:
        passes_updated_since = request.args["passesUpdatedSince"]
        passes = []
        logger.debug(
            f"filtering registered passes ({registration=}) with {passes_updated_since=}"
        )
        for membership_card in membership_cards:
            if membership_card.time_updated >= passes_updated_since:
                passes.append(membership_card)
                logger.debug(
                    f"{membership_card.time_updated} >= {passes_updated_since}"
                )
            else:
                logger.debug(f"{membership_card.time_updated} < {passes_updated_since}")
        logger.debug(
            f"after filtering registration with {passes_updated_since=}: {passes=}) "
        )

    if passes:
        logger.debug(
            f"found passes for {registration=}: {passes=}",
            extra=log_extra,
        )
        response = jsonify(
            {
                "lastUpdated": passes[0].time_updated,
                "serialNumbers": [p.apple_pass_serial_number for p in passes],
            }
        )
        logger.debug(
            f"sending response: {response}",
            extra=log_extra,
        )
        return response

    else:
        logger.info(
            f"no {passes=} left to return for {device_library_identifier=} ({pass_type_identifier=})!",
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
        user_email=membership_card_pass.user.email,
    )
    if modified_since_header := request.headers.get("If-Modified-Since"):
        logger.debug(
            f"parsing modified since header: {modified_since_header}", extra=log_extra
        )
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

    from member_card.passes import get_apple_pass_from_card

    attachment_filename = (
        f"lv_apple_pass-{membership_card_pass.user.last_name.lower()}.pkpass"
    )
    logger.info(
        f"generating updated pass for {membership_card_pass.user=}",
        extra=log_extra,
    )

    pkpass_out_path = get_apple_pass_from_card(
        membership_card=membership_card_pass,
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
        user_email=membership_card_pass.user.email,
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
        r"\[(?P<datetime_str>[0-9]{4}-[0-9]{2}-[0-9]{2}.*)\] (?P<task_name>[^(]+) \(for device (?P<device_id>[^,]+), pass type (?P<pass_type>[^,]+), serial number (?P<serial_num>[0-9]+); with web service url (?P<service_url>[^)]+)\) encountered error: (?P<error_msg>.*)"  # noqa
    ),
    re.compile(
        r"\[(?P<datetime_str>[0-9]{4}-[0-9]{2}-[0-9]{2}.*)\] (?P<task_name>[^(]+) \(pass type (?P<pass_type>[^,]+), serial number (?P<serial_num>[0-9]+), if-modified-since (?P<if_modified_since>[^;]+); with web service url (?P<service_url>[^)]+)\) encountered error: (?P<error_msg>.*)"  # noqa
    ),
    # TODO: nother one to add here:
    # [2022-02-10 14:35:57 -0600] Get serial #s task (for device 67cdbaff6b4fddc7df72e25e63d033f6, pass type
    # pass.es.losverd.card, last updated (null); with web service url https://card.losverd.es/passkit) encountered
    # error: Unexpected response code 500
]


@app.route("/passkit/v1/log", methods=["POST"])
def passkit_error_log():
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
