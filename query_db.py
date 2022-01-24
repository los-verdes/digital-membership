#!/usr/bin/env python
import logging

import logzero
from logzero import logger

from member_card.models import AnnualMembership

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
