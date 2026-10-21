class RagUnavailableError(Exception):
    def __init__(self):
        super().__init__("Assistant is temporarily unavailable")


class RagTimeoutError(Exception):
    def __init__(self):
        super().__init__("Assistant response timed out")


class RagBadResponseError(Exception):
    def __init__(self):
        super().__init__("Assistant returned an invalid response")