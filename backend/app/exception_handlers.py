from collections.abc import Awaitable, Callable
import logging

from app.auth.cookies import clear_tokens_cookie
from app.auth.errors import (
    AccessTokenNotFoundError,
    InvalidLoginCredentials,
    InvalidRefreshTokenError,
    InvalidTokenError,
    InvalidTokenTypeError,
    RefreshTokenNotFoundError,
)
from app.cards.errors import (
    CardAlreadyExistsError,
    CardNotFoundError,
)
from app.cards.errors import (
    PermissionDeniedError as CardPermissionDeniedError,
)
from app.decks.errors import (
    CannotFavouriteUnsavedDeckError,
    CannotSaveOwnDeckError,
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckIsEmptyError,
    DeckIsNotFavouriteError,
    DeckIsNotSavedError,
    DeckNotFoundError,
    DeckNotArchivedError,
    DeckSizeLimitExceededError,
    InvalidDeckCardPositionError,
    UserDeckNotFoundError,
)
from app.decks.archiver import ArchiveExpiredError, DeckProgressConflictError
from app.decks.errors import (
    PermissionDeniedError as DeckPermissionDeniedError,
)
from app.errors import (
    MetricsAccessDeniedError,
    RequestValueError,
)
from app.redis.errors import RateLimitError
from app.training_sessions.errors import (
    CardAlreadyAnsweredError,
    TrainingSessionAlreadyExistsError,
    TrainingSessionAlreadyFinishedError,
    TrainingSessionDeckArchivedError,
    TrainingSessionDeckUnavailableError,
    TrainingSessionItemNotFoundError,
    TrainingSessionNotFinishedYet,
    TrainingSessionNotFoundError,
)
from app.training_sessions.errors import (
    PermissionDeniedError as TrainingSessionPermissionDeniedError,
)
from app.users.errors import (
    PermissionDeniedError as UserPermissionDeniedError,
)
from app.users.errors import (
    EmailAlreadyExistsError,
    UserAlreadyExistsError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

type ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]

VALIDATION_ERROR_CODE = "VALIDATION_ERROR"

# Контракт с клиентом: code стабилен и по нему различают ошибки,
# message остаётся свободным текстом. Один и тот же статус несут разные
# ошибки, поэтому статуса для этого недостаточно.
ERROR_RESPONSES: tuple[tuple[type[Exception], int, str], ...] = (
    (InvalidLoginCredentials, status.HTTP_404_NOT_FOUND, "INVALID_LOGIN_CREDENTIALS"),
    (InvalidTokenError, status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN"),
    (InvalidTokenTypeError, status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN_TYPE"),
    (RefreshTokenNotFoundError, status.HTTP_401_UNAUTHORIZED, "REFRESH_TOKEN_NOT_FOUND"),
    (AccessTokenNotFoundError, status.HTTP_401_UNAUTHORIZED, "ACCESS_TOKEN_NOT_FOUND"),
    (MetricsAccessDeniedError, status.HTTP_401_UNAUTHORIZED, "METRICS_ACCESS_DENIED"),

    (UserNotFoundError, status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND"),
    (UserAlreadyExistsError, status.HTTP_409_CONFLICT, "USER_ALREADY_EXISTS"),
    (EmailAlreadyExistsError, status.HTTP_409_CONFLICT, "EMAIL_ALREADY_EXISTS"),
    (UsernameAlreadyExistsError, status.HTTP_409_CONFLICT, "USERNAME_ALREADY_EXISTS"),
    (UserPermissionDeniedError, status.HTTP_403_FORBIDDEN, "USER_PERMISSION_DENIED"),

    (CardNotFoundError, status.HTTP_404_NOT_FOUND, "CARD_NOT_FOUND"),
    (CardAlreadyExistsError, status.HTTP_409_CONFLICT, "CARD_ALREADY_EXISTS"),
    (CardPermissionDeniedError, status.HTTP_403_FORBIDDEN, "CARD_PERMISSION_DENIED"),

    (DeckNotFoundError, status.HTTP_404_NOT_FOUND, "DECK_NOT_FOUND"),
    (DeckNotArchivedError, status.HTTP_409_CONFLICT, "DECK_NOT_ARCHIVED"),
    (DeckAlreadyExistsError, status.HTTP_409_CONFLICT, "DECK_ALREADY_EXISTS"),
    (DeckIsEmptyError, status.HTTP_409_CONFLICT, "DECK_IS_EMPTY"),
    (DeckCardNotFoundError, status.HTTP_404_NOT_FOUND, "DECK_CARD_NOT_FOUND"),
    (InvalidDeckCardPositionError, status.HTTP_409_CONFLICT, "INVALID_DECK_CARD_POSITION"),
    (DeckCardAlreadyExistsError, status.HTTP_409_CONFLICT, "DECK_CARD_ALREADY_EXISTS"),
    (DeckSizeLimitExceededError, status.HTTP_409_CONFLICT, "DECK_SIZE_LIMIT_EXCEEDED"),
    (DeckPermissionDeniedError, status.HTTP_403_FORBIDDEN, "DECK_PERMISSION_DENIED"),
    (ArchiveExpiredError, status.HTTP_410_GONE, "ARCHIVE_EXPIRED"),
    (DeckProgressConflictError, status.HTTP_409_CONFLICT, "DECK_PROGRESS_CONFLICT"),
    (UserDeckNotFoundError, status.HTTP_404_NOT_FOUND, "USER_DECK_NOT_FOUND"),
    (DeckIsNotSavedError, status.HTTP_409_CONFLICT, "DECK_IS_NOT_SAVED"),
    (
        CannotFavouriteUnsavedDeckError,
        status.HTTP_409_CONFLICT,
        "CANNOT_FAVOURITE_UNSAVED_DECK",
    ),
    (DeckIsNotFavouriteError, status.HTTP_409_CONFLICT, "DECK_IS_NOT_FAVOURITE"),
    (CannotSaveOwnDeckError, status.HTTP_409_CONFLICT, "CANNOT_SAVE_OWN_DECK"),

    (TrainingSessionNotFoundError, status.HTTP_404_NOT_FOUND, "TRAINING_SESSION_NOT_FOUND"),
    (
        TrainingSessionItemNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "TRAINING_SESSION_ITEM_NOT_FOUND",
    ),
    (CardAlreadyAnsweredError, status.HTTP_409_CONFLICT, "CARD_ALREADY_ANSWERED"),
    (
        TrainingSessionAlreadyExistsError,
        status.HTTP_409_CONFLICT,
        "TRAINING_SESSION_ALREADY_EXISTS",
    ),
    (
        TrainingSessionAlreadyFinishedError,
        status.HTTP_409_CONFLICT,
        "TRAINING_SESSION_ALREADY_FINISHED",
    ),
    (TrainingSessionNotFinishedYet, status.HTTP_409_CONFLICT, "TRAINING_SESSION_NOT_FINISHED"),
    (
        TrainingSessionDeckArchivedError,
        status.HTTP_409_CONFLICT,
        "TRAINING_SESSION_DECK_ARCHIVED",
    ),
    (
        TrainingSessionDeckUnavailableError,
        status.HTTP_410_GONE,
        "TRAINING_SESSION_DECK_UNAVAILABLE",
    ),
    (
        TrainingSessionPermissionDeniedError,
        status.HTTP_403_FORBIDDEN,
        "TRAINING_SESSION_PERMISSION_DENIED",
    ),

    (RateLimitError, status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMIT_EXCEEDED"),
)


def make_error_handler(status_code: int, code: str) -> ExceptionHandler:
    async def error_handler(request: Request, exc: Exception) -> Response:
        return JSONResponse(
            status_code=status_code,
            content={
                "code": code,
                "message": str(exc),
            },
        )

    return error_handler


async def invalid_refresh_token_handler(
    request: Request,
    exc: InvalidRefreshTokenError,
):
    json_response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "code": "INVALID_REFRESH_TOKEN",
            "message": str(exc),
        },
    )
    clear_tokens_cookie(json_response)
    return json_response


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error",
        },
    )

logger = logging.getLogger(__name__)
async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
):
    logger.debug(exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "code": VALIDATION_ERROR_CODE,
            "message": "Validation error",
            "details": exc.errors(),
        },
    )


async def request_value_error_handler(
    request: Request,
    exc: RequestValueError,
):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "code": VALIDATION_ERROR_CODE,
            "message": "Validation error",
            "details": [
                {
                    "type": "value_error",
                    "loc": ["body", exc.failed_field],
                    "msg": str(exc),
                    "input": None,
                }
            ],
        },
    )


def register_exception_handlers(app: FastAPI):
    for exception_class, status_code, code in ERROR_RESPONSES:
        app.add_exception_handler(
            exception_class,
            make_error_handler(status_code=status_code, code=code),
        )

    app.add_exception_handler(InvalidRefreshTokenError, invalid_refresh_token_handler)
    app.add_exception_handler(RequestValueError, request_value_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
