import re
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import settings

# Patterns for write/DDL operations — rejected at the application layer
_DISALLOWED_PATTERNS = [
    re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE),
    re.compile(r"\b(DROP|CREATE|ALTER|TRUNCATE|RENAME)\b", re.IGNORECASE),
    re.compile(r"\b(GRANT|REVOKE|DENY)\b", re.IGNORECASE),
    re.compile(r"\b(COPY|EXECUTE|CALL|DO)\b", re.IGNORECASE),
]


@dataclass
class QueryResult:
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    sql_used: str = ""
    error: str | None = None
    was_truncated: bool = False
    row_count: int = 0


def validate_sql(sql: str) -> tuple[bool, str]:
    stripped = sql.strip()
    if not stripped:
        return False, "Empty query."

    # First token must be SELECT or WITH (for CTEs)
    first_token = stripped.split()[0].upper()
    if first_token not in ("SELECT", "WITH"):
        return False, f"Only SELECT queries are allowed. Got: {first_token}"

    # WITH statements must eventually lead to SELECT, not DML
    for pattern in _DISALLOWED_PATTERNS:
        if pattern.search(stripped):
            match = pattern.search(stripped)
            return False, f"Query contains disallowed keyword: {match.group()}"

    # Reject multi-statement attempts
    # A semicolon not at the very end is suspicious
    no_trailing = stripped.rstrip(";").rstrip()
    if ";" in no_trailing:
        return False, "Multi-statement queries are not allowed."

    return True, ""


def execute_query(sql: str, session: Session) -> tuple[pd.DataFrame, str | None]:
    timeout_ms = settings.QUERY_TIMEOUT_SECONDS * 1000
    row_limit = settings.QUERY_ROW_LIMIT

    try:
        # Set statement timeout for this transaction
        session.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}ms'"))

        result = session.execute(text(sql))
        columns = list(result.keys())

        # Fetch one extra row to detect truncation
        rows = result.fetchmany(row_limit + 1)
        session.rollback()

        was_truncated = len(rows) > row_limit
        rows = rows[:row_limit]

        df = pd.DataFrame(rows, columns=columns)
        return df, None

    except Exception as e:
        try:
            session.rollback()
        except Exception:
            pass
        return pd.DataFrame(), str(e)


def run_query(sql: str) -> QueryResult:
    from db.connection import get_session

    is_valid, reason = validate_sql(sql)
    if not is_valid:
        return QueryResult(sql_used=sql, error=f"Validation error: {reason}")

    with get_session() as session:
        df, error = execute_query(sql, session)

    if error:
        return QueryResult(sql_used=sql, error=error)

    was_truncated = len(df) == settings.QUERY_ROW_LIMIT
    return QueryResult(
        df=df,
        sql_used=sql,
        error=None,
        was_truncated=was_truncated,
        row_count=len(df),
    )
