#!/usr/bin/env python
import logging

import logzero
from logzero import logger

from member_card.db import get_firestore_client
from member_card.squarespace import AnnualMembership

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-q",
        "--quiet",
        help="modify output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "-e",
        "--email",
        default="jeff.hogan1@gmail.com",
    )
    parser.add_argument(
        "-f",
        "--fulfillment-status",
        choices=["PENDING", "FULFILLED", "CANCELED", None],
        default=None,
    )
    args = parser.parse_args()
    if args.quiet:
        logzero.loglevel(logging.INFO)

    email = args.email

    db = get_firestore_client()
    memberships_ref = db.collection("memberships")
    memberships = memberships_ref.where('email', '==', email)
    for membership in memberships.stream():
        logger.info(f'{membership.id} => {membership.to_dict()}')
        m = AnnualMembership.from_dict(membership.to_dict())
        logger.info(f'{email} => {m=}')
