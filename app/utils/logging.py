"""Safe-logging setup: a best-effort redaction net so PII-shaped values
never reach stdout even if a future caller passes them by mistake.

This is not a substitute for discipline at call sites — services must not
pass raw PII into log messages in the first place. See CLAUDE.md security
rules: never log passport numbers, names, DOB, face images, raw documents,
encryption keys, or auth tokens.
"""
import logging
import re

_REDACT_PATTERNS = [
    re.compile(r"\b\d{6,}\b"),  # long digit runs: passport/Aadhaar/phone-shaped numbers
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern in _REDACT_PATTERNS:
            msg = pattern.sub("[REDACTED]", msg)
        record.msg = msg
        record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
