#!/usr/bin/env python
import os
import logging

import click

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
        return {
            "timestamp": self.format_timestamp(record.asctime),
            "severity": self.format_severity(record.levelname),
            "message": record.getMessage(),
            "labels": self.make_labels(),
            "metadata": self.make_metadata(record),
            "sourceLocation": self.make_source_location(record),
            "logging.googleapis.com/trace": inferred_trace,
            "span_id": inferred_span,
            "http_request": inferred_http,
        }


class RemoveColorFilter(logging.Filter):
    def filter(self, record):
        if record and record.msg and isinstance(record.msg, str):
            record.msg = click.unstyle(record.msg)
        return True


log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging_handlers = ["default"]
logging_handlers = ["json"]
running_on_cloud_run = "K_SERVICE" in os.environ
if running_on_cloud_run:
    logging_handlers = ["json"]

dictConfig(
    {
        "version": 1,
        "filters": {
            "no_color": {
                "()": RemoveColorFilter,
            }
        },
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
                "filters": ["no_color"],
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

# logging_handlers = ["default"]
# logging_handlers = ["gcloud"]
# if running_on_cloud_run := "K_SERVICE" in os.environ:
#     logging_handlers = ["gcloud"]
# dictConfig(
#     {
#         "version": 1,
#         # "filters": {
#         #     "no_color": {
#         #         "()": RemoveColorFilter,
#         #     }
#         # },
#         "formatters": {
#             # "json": {
#             #     "()": "google.cloud.logging.handlers.StructuredLogHandler",
#             #     "application_info": {
#             #         "type": "python-application",
#             #         "name": "digital-membership",
#             #     },
#             #     "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
#             # },
#             "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
#         },
#         "handlers": {
#             "default": {
#                 "level": "INFO",
#                 "formatter": "standard",
#                 "class": "logging.StreamHandler",
#                 "stream": "ext://sys.stdout",
#             },
#             "gcloud": {
#                 "class": StructuredLogHandler(),
#                 # "formatter": "json",
#             },
#         },
#         "loggers": {
#             "": {
#                 "level": os.getenv("LOG_LEVEL", "INFO").upper(),
#                 "handlers": logging_handlers,
#                 "propagate": False,
#             },
#             "member_card": {
#                 "level": os.getenv("LOG_LEVEL", "INFO").upper(),
#                 "handlers":  logging_handlers,
#             },
#         },
#     }
# )
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    app = create_app()
    app.run()
