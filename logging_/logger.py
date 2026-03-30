import json
import logging
import os
from datetime import datetime, timezone

from config.settings import settings


def setup_logger() -> logging.Logger:
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)

    logger = logging.getLogger("db_agent")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

    if not logger.handlers:
        # File handler — JSON lines
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(file_handler)

        # Console handler — human-readable
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
        )
        logger.addHandler(console_handler)

    return logger


_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def log_turn(result) -> None:
    logger = get_logger()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": result.question,
        "final_answer_length": len(result.final_answer),
        "sql_attempts": result.sql_attempts,
        "final_sql": result.final_sql,
        "row_count": len(result.result_df) if result.result_df is not None else 0,
        "was_truncated": result.was_truncated,
        "error": result.error,
        "duration_seconds": round(result.duration_seconds, 3),
        "token_usage": result.token_usage,
    }
    # Write as JSON line to file handler, plain text to console
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.stream.write(json.dumps(record) + "\n")
            handler.stream.flush()
        else:
            status = "ERROR" if result.error else "OK"
            handler.emit(logging.LogRecord(
                name="db_agent",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"[{status}] q={repr(result.question[:60])} rows={record['row_count']} t={record['duration_seconds']}s tokens={result.token_usage}",
                args=(),
                exc_info=None,
            ))
