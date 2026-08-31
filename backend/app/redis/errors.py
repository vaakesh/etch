class RateLimitError(Exception):
    def __init__(
        self,
        message: str = "Too many requests. Please try again later.",
    ):
        super().__init__(message)
