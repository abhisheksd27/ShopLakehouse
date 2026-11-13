"""Small structured logger without data rows or credentials."""

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "context"):
            item.update(record.context)
        if record.exc_info and record.exc_info[0]:
            item["error_type"] = record.exc_info[0].__name__
        return json.dumps(item, default=str)


def configure() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ("great_expectations", "py4j", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)
