class DeckNotFoundError(Exception):
    def __init__(self, message: str = "Deck not found"):
        super().__init__(message)


class DeckNotArchivedError(Exception):
    def __init__(self, message: str = "Deck is not archived"):
        super().__init__(message)


class UserDeckNotFoundError(Exception):
    def __init__(self, message: str = "User deck progress not found"):
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


class DeckIsNotSavedError(Exception):
    def __init__(self, message: str = "Deck is not saved"):
        super().__init__(message)


class CannotFavouriteUnsavedDeckError(Exception):
    def __init__(self, message: str = "Save the deck before adding it to favourites"):
        super().__init__(message)


class DeckIsNotFavouriteError(Exception):
    def __init__(self, message: str = "Deck is not in favourites"):
        super().__init__(message)


class CannotSaveOwnDeckError(Exception):
    def __init__(self, message: str = "You cannot save your own deck"):
        super().__init__(message)


class DeckIsEmptyError(Exception):
    def __init__(self, message: str = "Deck is empty"):
        super().__init__(message)


class InvalidDeckCardPositionError(Exception):
    def __init__(self, message: str = "Invalid card position in deck"):
        super().__init__(message)


class DeckSizeLimitExceededError(Exception):
    def __init__(
            self,
            limit: int,
            current: int,
            requested: int,
        ):
        remaining = max(limit - current, 0)
        message = (
            f"Deck size limit exceeded: deck has {current}/{limit} cards, "
            f"cannot add {requested} more (only {remaining} slots left)"
        )
        super().__init__(message)
