"""Structured (JSON) logging for the WhatsApp webhook.

Keeps patient identifiers out of logs in clear text (docs/spec.md section 3:
"logs sin PII en claro"): phone numbers are reduced to a short one-way hash
so the same patient can be correlated across log lines without storing the
real number.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

# Standard attributes present on every LogRecord. Anything else found on a
# record (passed via `extra=`) is application data and gets included in the
# JSON output.
_STANDARD_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message",
}


class JsonFormatter(logging.Formatter):
    """Format each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def hash_phone(phone: str) -> str:
    """Return a short one-way hash of a phone number for log correlation."""
    return hashlib.sha256(phone.encode()).hexdigest()[:12]


def configure_logging() -> None:
    """Configure the root logger to emit JSON lines on stdout."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
