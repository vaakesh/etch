import logging
import re
import sys
import textwrap
import time
from copy import copy
from contextvars import ContextVar, Token
from dataclasses import dataclass
from http import HTTPStatus
from pprint import pformat
from typing import Any
from urllib.parse import parse_qsl, urlencode
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.engine import Connection, ExceptionContext
from sqlalchemy.engine.interfaces import ExecutionContext
from sqlalchemy.ext.asyncio import AsyncEngine
from opentelemetry import trace

LOG_FORMAT = (
    "%(asctime)s.%(msecs)03dZ | %(levelname)s | "
    "%(name)s:%(lineno)d | "
    "req=%(request_id)s | "
    "trace=%(trace_id)s | span=%(span_id)s | "
    "%(message)s"
)
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

RESET = "\x1b[0m"

COLORS = {
    logging.DEBUG: "\x1b[37m",      # white
    logging.INFO: "\x1b[32m",       # green
    logging.WARNING: "\x1b[33m",    # yellow
    logging.ERROR: "\x1b[31m",      # red
    logging.CRITICAL: "\x1b[1;31m", # bold red
}

SQL_LOGGER = logging.getLogger("app.sql")
SQL_START_TIMES_KEY = "etch_sql_start_times"
SQL_TRANSACTION_ID_KEY = "etch_sql_transaction_id"
SQL_LINE_WIDTH = 100
SQL_CLAUSE_PATTERN = re.compile(
    r"\s+(?=(?:"
    r"LEFT(?:\s+OUTER)?\s+JOIN|RIGHT(?:\s+OUTER)?\s+JOIN|"
    r"FULL(?:\s+OUTER)?\s+JOIN|INNER\s+JOIN|CROSS\s+JOIN|"
    r"FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|"
    r"FETCH|RETURNING|VALUES|SET|ON\s+CONFLICT|UNION(?:\s+ALL)?"
    r")\b)",
    flags=re.IGNORECASE,
)
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
SENSITIVE_QUERY_FIELDS = frozenset({
    "access_token",
    "api_key",
    "authorization",
    "code",
    "password",
    "refresh_token",
    "secret",
    "token",
})
LOGGED_EXCEPTION_ATTRIBUTE = "_etch_already_logged"


@dataclass(slots=True, frozen=True)
class RequestLogContext:
    request_id: str
    method: str
    path: str


request_log_context: ContextVar[RequestLogContext | None] = ContextVar(
    "request_log_context",
    default=None,
)


@dataclass(slots=True, frozen=True)
class SQLLoggingConfig:
    enabled: bool = True
    show_parameters: bool = False
    slow_query_ms: float = 200.0


sql_logging_config = SQLLoggingConfig()


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if _is_duplicate_uvicorn_exception(record):
            return False

        context = request_log_context.get()
        record.request_id = context.request_id if context else "-"
        span_context = trace.get_current_span().get_span_context()
        record.trace_id = (
            format(span_context.trace_id, "032x")
            if span_context.is_valid
            else "-"
        )
        record.span_id = (
            format(span_context.span_id, "016x")
            if span_context.is_valid
            else "-"
        )
        return True


class ColoredFormatter(logging.Formatter):
    RESET = RESET
    COLORS = COLORS
    converter = time.gmtime

    def __init__(
        self,
        *args: Any,
        use_colors: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        formatted_record = copy(record)
        level_name = f"{record.levelname:<8}"

        if self.use_colors:
            color = self.COLORS.get(record.levelno, self.RESET)
            formatted_record.levelname = (
                f"{color}{level_name}{self.RESET}"
            )
        else:
            formatted_record.levelname = level_name

        return super().format(formatted_record)


def _is_duplicate_uvicorn_exception(record: logging.LogRecord) -> bool:
    if record.name != "uvicorn.error" or not record.exc_info:
        return False

    exception = record.exc_info[1]
    return bool(
        exception
        and getattr(exception, LOGGED_EXCEPTION_ATTRIBUTE, False)
    )


def _single_line(value: str) -> str:
    return value.replace("\r", "\\r").replace("\n", "\\n")


def format_log_value(value: str, *, max_length: int = 500) -> str:
    formatted_value = _single_line(value)
    if len(formatted_value) <= max_length:
        return formatted_value

    return f"{formatted_value[:max_length]}..."


def format_query_string(query_string: str) -> str:
    if not query_string:
        return "-"

    try:
        query_items = parse_qsl(
            query_string,
            keep_blank_values=True,
            max_num_fields=100,
        )
    except ValueError:
        return "<invalid>"

    safe_query_items = [
        (
            name,
            "REDACTED" if name.lower() in SENSITIVE_QUERY_FIELDS else value,
        )
        for name, value in query_items
    ]
    return format_log_value(
        urlencode(safe_query_items),
        max_length=2000,
    )


def format_http_status(status_code: int) -> str:
    try:
        reason = HTTPStatus(status_code).phrase
    except ValueError:
        return str(status_code)

    return f"{status_code} {reason}"


def mark_exception_as_logged(exception: BaseException) -> None:
    try:
        setattr(exception, LOGGED_EXCEPTION_ATTRIBUTE, True)
    except (AttributeError, TypeError):
        pass


def _get_request_id(received_request_id: str | None) -> str:
    if received_request_id and REQUEST_ID_PATTERN.fullmatch(received_request_id):
        return received_request_id

    return uuid4().hex


def bind_request_context(
    *,
    received_request_id: str | None,
    method: str,
    path: str,
) -> tuple[
    RequestLogContext,
    Token[RequestLogContext | None],
]:
    context = RequestLogContext(
        request_id=_get_request_id(received_request_id),
        method=_single_line(method),
        path=_single_line(path),
    )
    return context, request_log_context.set(context)


def reset_request_context(
    token: Token[RequestLogContext | None],
) -> None:
    request_log_context.reset(token)


def _format_sql_statement(statement: str) -> str:
    formatted_lines: list[str] = []

    for raw_line in statement.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue

        for clause_line in SQL_CLAUSE_PATTERN.split(line):
            formatted_lines.extend(
                textwrap.wrap(
                    clause_line,
                    width=SQL_LINE_WIDTH,
                    subsequent_indent="    ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )

    return "\n".join(formatted_lines)


def _format_sql_parameters(parameters: Any) -> str:
    if not sql_logging_config.show_parameters:
        return "<hidden>"

    return pformat(
        parameters,
        width=SQL_LINE_WIDTH,
        compact=True,
        sort_dicts=False,
    )


def _indent_log_block(value: str) -> str:
    return textwrap.indent(value, "    ")


def _get_sql_transaction_id(connection: Connection | None) -> str:
    if connection is None:
        return "-"

    return connection.info.get(SQL_TRANSACTION_ID_KEY, "-")


def _log_transaction_begin(connection: Connection) -> None:
    if not sql_logging_config.enabled:
        return

    transaction_id = uuid4().hex[:8]
    connection.info[SQL_TRANSACTION_ID_KEY] = transaction_id
    SQL_LOGGER.info(
        "TRANSACTION BEGIN | transaction_id=%s",
        transaction_id,
    )


def _log_transaction_commit(connection: Connection) -> None:
    if not sql_logging_config.enabled:
        return

    SQL_LOGGER.info(
        "TRANSACTION COMMIT | transaction_id=%s",
        _get_sql_transaction_id(connection),
    )


def _log_transaction_rollback(connection: Connection) -> None:
    if not sql_logging_config.enabled:
        return

    SQL_LOGGER.info(
        "TRANSACTION ROLLBACK | transaction_id=%s",
        _get_sql_transaction_id(connection),
    )


def _start_sql_timer(
    connection: Connection,
    _cursor: Any,
    _statement: str,
    _parameters: Any,
    _context: ExecutionContext,
    _executemany: bool,
) -> None:
    if not sql_logging_config.enabled:
        return

    connection.info.setdefault(SQL_START_TIMES_KEY, []).append(
        time.perf_counter()
    )


def _pop_sql_start_time(connection: Connection | None) -> float | None:
    if connection is None:
        return None

    start_times = connection.info.get(SQL_START_TIMES_KEY)
    if not start_times:
        return None

    started_at = start_times.pop()
    if not start_times:
        connection.info.pop(SQL_START_TIMES_KEY, None)

    return started_at


def _log_executed_sql(
    connection: Connection,
    _cursor: Any,
    statement: str,
    parameters: Any,
    _context: ExecutionContext,
    _executemany: bool,
) -> None:
    started_at = _pop_sql_start_time(connection)
    if started_at is None:
        return

    duration_ms = (time.perf_counter() - started_at) * 1000
    log_method = (
        SQL_LOGGER.warning
        if duration_ms >= sql_logging_config.slow_query_ms
        else SQL_LOGGER.info
    )
    log_method(
        "SQL completed\n"
        "  transaction_id: %s\n"
        "  duration_ms: %.2f\n"
        "  statement:\n%s\n"
        "  parameters:\n%s",
        _get_sql_transaction_id(connection),
        duration_ms,
        _indent_log_block(_format_sql_statement(statement)),
        _indent_log_block(_format_sql_parameters(parameters)),
    )


def _log_failed_sql(exception_context: ExceptionContext) -> None:
    statement = exception_context.statement
    started_at = _pop_sql_start_time(exception_context.connection)

    if statement is None or started_at is None:
        return

    duration_ms = (time.perf_counter() - started_at) * 1000
    SQL_LOGGER.error(
        "SQL failed\n"
        "  transaction_id: %s\n"
        "  duration_ms: %.2f\n"
        "  error: %s\n"
        "  statement:\n%s\n"
        "  parameters:\n%s",
        _get_sql_transaction_id(exception_context.connection),
        duration_ms,
        type(exception_context.original_exception).__name__,
        _indent_log_block(_format_sql_statement(statement)),
        _indent_log_block(
            _format_sql_parameters(exception_context.parameters)
        ),
    )


def _setup_sql_logging(engine: AsyncEngine) -> None:
    sync_engine = engine.sync_engine
    listeners = (
        ("begin", _log_transaction_begin),
        ("commit", _log_transaction_commit),
        ("rollback", _log_transaction_rollback),
        ("before_cursor_execute", _start_sql_timer),
        ("after_cursor_execute", _log_executed_sql),
        ("handle_error", _log_failed_sql),
    )

    for event_name, listener in listeners:
        if not event.contains(sync_engine, event_name, listener):
            event.listen(sync_engine, event_name, listener)


def setup_logging(
    *,
    log_sql: bool = True,
    log_sql_parameters: bool = False,
    slow_query_ms: float = 200.0,
    use_colors: bool | None = None,
) -> None:
    global sql_logging_config

    if slow_query_ms < 0:
        raise ValueError("slow_query_ms must be greater than or equal to zero")

    sql_logging_config = SQLLoggingConfig(
        enabled=log_sql,
        show_parameters=log_sql_parameters,
        slow_query_ms=slow_query_ms,
    )

    if use_colors is None:
        use_colors = sys.stdout.isatty()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(
        ColoredFormatter(
            fmt=LOG_FORMAT,
            datefmt=DATE_FORMAT,
            use_colors=use_colors,
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]

    for name in (
        "uvicorn",
        "uvicorn.error",
        "fastapi",
        "sqlalchemy.engine",
        "sqlalchemy.pool"
    ):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers = []
    uvicorn_access_logger.propagate = False
    uvicorn_access_logger.disabled = True

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if log_sql:
        from app.database import get_engine

        _setup_sql_logging(get_engine())
