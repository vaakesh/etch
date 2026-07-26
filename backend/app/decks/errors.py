class DeckNotFoundError(Exception):
    def __init__(self, message: str = "Deck not found"):
        super().__init__(message)


class DeckAlreadyExistsError(Exception):
    def __init__(self, message: str = "Deck already exists"):
        super().__init__(message)


class DeckCardNotFoundError(Exception):
    def __init__(self, message: str = "Deck card link not found"):
        super().__init__(message)


class DeckCardAlreadyExistsError(Exception):
    def __init__(self, message: str = "Card already exists in this deck"):
        super().__init__(message)


class PermissionDeniedError(Exception):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)


class DeckIsNotFollowedError(Exception):
    def __init__(self, message: str = "Deck is not followed"):
        super().__init__(message)


class CannotFollowOwnDeckError(Exception):
    def __init__(self, message: str = "Your own deck can't be followed"):
        super().__init__(message)


class DeckIsEmptyError(Exception):
    def __init__(self, message: str = "Deck is empty"):
        super().__init__(message)

class InvalidDeckCardPositionError(Exception):
    def __init__(self, message: str = "Invalid card position in deck"):
            super().__init__(message)