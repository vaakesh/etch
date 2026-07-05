class CardNotFoundError(Exception):
    def __init__(self, message: str = "Card not found"):
        super().__init__(message)


class CardAlreadyExistsError(Exception):
    def __init__(self, message: str = "Card already exists"):
        super().__init__(message)


class PermissionDeniedError(Exception):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)