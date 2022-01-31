#!/usr/bin/env python
import os
import logging


from member_card import create_app
from google.cloud.logging_v2.handlers._helpers import get_request_data
from logging.config import dictConfig
from google_cloud_logger import GoogleCloudFormatter

try:
    import googleclouddebugger

    googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
    pass


class MemberCardFormatter(GoogleCloudFormatter):
    """
    https://cloud.google.com/run/docs/logging#using-json
    """

    # The subset of http_request fields have been tested to work consistently across GCP environments
    # https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#httprequest
    _supported_http_fields = ("requestMethod", "requestUrl", "userAgent", "protocol")

    def __init__(self, *args, **kwargs):
        self.gcp_project = kwargs.pop("gcp_project", {})
        super(MemberCardFormatter, self).__init__(*args, **kwargs)

    def make_entry(self, record):
        inferred_http, inferred_trace, inferred_span = get_request_data()
        if inferred_http is not None:
            # filter inferred_http to include only well-supported fields
            inferred_http = {
                k: v
                for (k, v) in inferred_http.items()
                if k in self._supported_http_fields and v is not None
            }
        if inferred_trace is not None and self.gcp_project is not None:
            # add full path for detected trace
            inferred_trace = f"projects/{self.gcp_project}/traces/{inferred_trace}"
        entry = {
            "timestamp": self.format_timestamp(record.asctime),
            "severity": self.format_severity(record.levelname),
            "message": record.getMessage(),
            "labels": self.make_labels(),
            "metadata": self.make_metadata(record),
            "sourceLocation": self.make_source_location(record),
        }
        if inferred_trace:
            entry.update(
                {
                    "logging.googleapis.com/trace": inferred_trace,
                    "span_id": inferred_span,
                    "http_request": inferred_http,
                }
            )
        return entry


log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging_handlers = ["default"]
running_on_cloud_run = "K_SERVICE" in os.environ
if running_on_cloud_run:
    logging_handlers = ["json"]

dictConfig(
    {
        "version": 1,
        "formatters": {
            "json": {
                "()": "wsgi.MemberCardFormatter",
                "application_info": {
                    "type": "python-application",
                    "name": "digital-membership",
                },
                "gcp_project": os.getenv("GCLOUD_PROJECT", ""),
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            },
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "default": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "json": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "loggers": {
            "": {
                "level": log_level,
                "handlers": logging_handlers,
                "propagate": False,
            },
            "member_card": {
                "level": log_level,
                "handlers": logging_handlers,
            },
        },
    }
)

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    app = create_app()
    app.run()
