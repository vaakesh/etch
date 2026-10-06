"""Application spans without request values or exception messages."""

from contextlib import contextmanager
from functools import wraps
from inspect import iscoroutinefunction

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)


@contextmanager
def trace_span(name: str):
    with tracer.start_as_current_span(
        name, record_exception=False, set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except BaseException as error:
            # Database exception messages can contain bound passwords/email.
            error_type = type(error).__name__
            span.set_attribute("error.type", error_type)
            span.set_status(Status(StatusCode.ERROR))
            span.add_event("exception", {"exception.type": error_type})
            raise


def traced(name: str):
    """Preserve sync/async signatures and the current trace's parent span."""
    def decorate(function):
        if iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args, **kwargs):
                with trace_span(name):
                    return await function(*args, **kwargs)

            return async_wrapper

        @wraps(function)
        def sync_wrapper(*args, **kwargs):
            with trace_span(name):
                return function(*args, **kwargs)

        return sync_wrapper

    return decorate
