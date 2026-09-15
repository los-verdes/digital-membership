import json
import logging

import flask
import pytest
from wsgi import MemberCardFormatter

# matches the "json" formatter's "format" config in wsgi.py's dictConfig, which is
# what makes JsonFormatter populate record.asctime (needed by make_entry) in the
# first place
_FMT = "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"


def _make_record(msg="hello"):
    return logging.LogRecord(
        name="member_card",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


@pytest.fixture()
def formatter():
    return MemberCardFormatter(fmt=_FMT, gcp_project="fake-project")


def test_make_entry_outside_request_context(formatter):
    # e.g. worker/background logging, where no Flask request is active
    entry = json.loads(formatter.format(_make_record()))

    assert entry["message"] == "hello"
    assert "logging.googleapis.com/trace" not in entry


def test_make_entry_within_request_context(formatter):
    # regression test: google-cloud-logging>=3.x's get_request_data() returns
    # a 4-tuple (http_request, trace_id, span_id, trace_sampled) instead of the
    # 3-tuple returned by <3.x. Unpacking that 4-tuple into 3 names raised a
    # ValueError from inside Formatter.format() on every single log record
    # emitted while handling a request, which logging's default error handling
    # then dumped as a multi-line traceback (several log entries) to stderr in
    # place of the original message.
    request_app = flask.Flask(__name__)
    with request_app.test_request_context(
        "/some/path",
        headers={"X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/1;o=1"},
    ):
        entry = json.loads(formatter.format(_make_record()))

    assert entry["message"] == "hello"
    assert entry["http_request"]["requestUrl"].endswith("/some/path")
    assert entry["logging.googleapis.com/trace"] == (
        "projects/fake-project/traces/105445aa7843bc8bf206b12000100000"
    )
