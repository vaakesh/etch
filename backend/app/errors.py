class RequestValueError(Exception):
    def __init__(
            self, 
            message: str = "Failed to validate the value",
            failed_field: str | None = None,
        ):
        if failed_field and message == "Failed to validate the value":
            message = f"Failed to validate field '{failed_field}'"
        self.failed_field = failed_field
        super().__init__(message)


class MetricsAccessDeniedError(Exception):
    def __init__(self, message: str = "Invalid or missing metrics token"):
        super().__init__(message)
