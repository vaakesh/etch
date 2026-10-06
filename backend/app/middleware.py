import logging
import time
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager

from app.logging_config import (
    RequestLogContext,
    bind_request_context,
    format_log_value,
    format_query_string,
    mark_exception_as_logged,
    reset_request_context,
)
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(name=__name__)


http_requests_all_total = Counter(
    name="http_requests_all_total",
    documentation=(
        "Total number of incoming HTTP requests across all methods, routes and statuses"
    ),
)
http_requests_by_method_total = Counter(
    name="http_requests_by_method_total",
    documentation="Total number of incoming HTTP requests by method",
    labelnames=["method"],
)
http_requests_total = Counter(
    name="http_requests_total",
    documentation="Total number of incoming HTTP requests",
    labelnames=["method", "route", "status"],
)
http_request_duration_seconds = Histogram(
    name="http_request_duration_seconds",
    documentation="HTTP request duration in seconds",
    labelnames=["method", "route", "status"],
    buckets=(
        0.01, 0.025, 0.05, 0.1, 0.2, 0.3,
        0.5, 1, 2, 5, 10,
    ),
)
http_requests_in_progress = Gauge(
    name="http_requests_in_progress",
    documentation="Number of HTTP requests currently being processed",
)


class LoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        context, context_token = bind_request_context(
            received_request_id=request.headers.get("X-Request-ID"),
            method=request.method,
            path=request.url.path,
        )
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000
            self._log_failed(
                request=request, context=context, exc=exc, duration_ms=duration_ms
            )
            raise
        else:
            duration_ms = (time.perf_counter() - started_at) * 1000
            response.headers["X-Request-ID"] = context.request_id
            self._log_completed(
                request=request, context=context, response=response,
                duration_ms=duration_ms,
            )
            return response
        finally:
            reset_request_context(token=context_token)

    def _log_failed(
        self,
        request: Request,
        context: RequestLogContext,
        exc: Exception,
        duration_ms: float,
    ) -> None:
        mark_exception_as_logged(exception=exc)
        logger.exception(
            "HTTP %s %s failed after %.2f ms",
            context.method,
            context.path,
            duration_ms,
            extra={
                "event": "http.request.failed",
                "http_method": context.method,
                "http_path": context.path,
                "http_query": format_query_string(request.url.query),
                "client_address": request.client.host if request.client else "-",
                "http_route": getattr(request.scope.get("route"), "path_format", None)
                or "unmatched",
                "http_status_code": 500,
                "duration_ms": duration_ms,
                "outcome": "server_error",
                "error_type": type(exc).__name__,
                "error_message": format_log_value(str(exc)),
            },
        )

    def _log_completed(
        self,
        request: Request,
        context: RequestLogContext,
        response: Response,
        duration_ms: float,
    ) -> None:
        if response.status_code >= 500:
            log_level = logging.ERROR
            outcome = "server_error"
        elif response.status_code >= 400:
            log_level = logging.WARNING
            outcome = "client_error"
        elif duration_ms >= 500:
            log_level = logging.WARNING
            outcome = "slow"
        else:
            log_level = logging.INFO
            outcome = "success"

        logger.log(
            log_level,
            "HTTP %s %s → %d in %.2f ms",
            context.method,
            context.path,
            response.status_code,
            duration_ms,
            extra={
                "event": "http.request.completed",
                "http_method": context.method,
                "http_path": context.path,
                "http_query": format_query_string(request.url.query),
                "client_address": request.client.host if request.client else "-",
                "http_route": getattr(request.scope.get("route"), "path_format", None)
                or "unmatched",
                "http_status_code": response.status_code,
                "duration_ms": duration_ms,
                "outcome": outcome,
            },
        )


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        self._count_all_requests()
        self._count_requests_by_method(method=request.method)
        started_at = time.perf_counter()
        status_code = 500

        with self._track_in_progress():
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            finally:
                duration_seconds = time.perf_counter() - started_at
                route = request.scope.get("route")
                route_template = getattr(route, "path_format", None) or "unmatched"
                self._count_requests(
                    method=request.method,
                    route=route_template,
                    status_code=status_code,
                )
                self._observe_duration(
                    method=request.method,
                    route=route_template,
                    status_code=status_code,
                    duration_seconds=duration_seconds,
                )

    def _count_all_requests(self) -> None:
        http_requests_all_total.inc()

    def _count_requests_by_method(self, method: str) -> None:
        http_requests_by_method_total.labels(method=method).inc()

    def _count_requests(self, method: str, route: str, status_code: int) -> None:
        http_requests_total.labels(
            method=method,
            route=route,
            status=str(status_code),
        ).inc()

    def _observe_duration(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        http_request_duration_seconds.labels(
            method=method,
            route=route,
            status=str(status_code),
        ).observe(amount=duration_seconds)

    @contextmanager
    def _track_in_progress(self) -> Generator[None]:
        http_requests_in_progress.inc()
        try:
            yield
        finally:
            http_requests_in_progress.dec()


def setup_middlewares(app: FastAPI) -> None:
    # the last middleware added runs first: logger -> prometheus -> router.
    app.add_middleware(middleware_class=PrometheusMiddleware)
    app.add_middleware(middleware_class=LoggerMiddleware)
