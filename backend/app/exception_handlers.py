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
    CannotSaveOwnDeckError,
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckIsEmptyError,
    DeckIsNotFavouriteError,
    DeckIsNotSavedError,
    DeckNotFoundError,
    InvalidDeckCardPositionError,
    UserDeckNotFoundError,
)
from app.decks.errors import (
    PermissionDeniedError as DeckPermissionDeniedError,
)
from app.errors import (
    RequestValueError,
)
from app.redis.errors import RateLimitError
from app.training_sessions.errors import (
    CardAlreadyAnsweredError,
    TrainingSessionAlreadyExistsError,
    TrainingSessionAlreadyFinishedError,
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
    UserAlreadyExistsError,
    UserNotFoundError,
)
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def invalid_login_credentials_handler(
    request: Request,
    exc: InvalidLoginCredentials,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def invalid_token_handler(
    request: Request,
    exc: InvalidTokenError,
):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "message": str(exc),
        },
    )

async def invalid_refresh_token_handler(
    request: Request,
    exc: InvalidRefreshTokenError,
):
    json_response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "message": str(exc),
        },
    )
    clear_tokens_cookie(json_response)
    return json_response


async def invalid_token_type_handler(
    request: Request,
    exc: InvalidTokenTypeError,
):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "message": str(exc),
        },
    )


async def refresh_token_not_found_handler(
    request: Request,
    exc: RefreshTokenNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "message": str(exc),
        },
    )


async def access_token_not_found_handler(
    request: Request,
    exc: AccessTokenNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "message": str(exc),
        },
    )


async def user_not_found_handler(
    request: Request,
    exc: UserNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def user_already_exists_handler(
    request: Request,
    exc: UserAlreadyExistsError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def user_permission_denied_handler(
    request: Request,
    exc: UserPermissionDeniedError,
):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "message": str(exc),
        },
    )


async def card_not_found_handler(
    request: Request,
    exc: CardNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def card_already_exists_handler(
    request: Request,
    exc: CardAlreadyExistsError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def card_permission_denied_handler(
    request: Request,
    exc: CardPermissionDeniedError,
):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "message": str(exc),
        },
    )


async def deck_not_found_handler(
    request: Request,
    exc: DeckNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def deck_already_exists_handler(
    request: Request,
    exc: DeckAlreadyExistsError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def deck_is_empty_handler(
    request: Request,
    exc: DeckIsEmptyError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )

async def deck_card_not_found_handler(
    request: Request,
    exc: DeckCardNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def invalid_deck_card_position_handler(
    request: Request,
    exc: InvalidDeckCardPositionError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def deck_card_already_exists_handler(
    request: Request,
    exc: DeckCardAlreadyExistsError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def deck_permission_denied_handler(
    request: Request,
    exc: DeckPermissionDeniedError,
):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "message": str(exc),
        },
    )


async def user_deck_not_found_handler(
    request: Request,
    exc: UserDeckNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def deck_is_not_saved_handler(
    request: Request,
    exc: DeckIsNotSavedError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def deck_is_not_favourite_handler(
    request: Request,
    exc: DeckIsNotFavouriteError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def cannot_save_own_deck_handler(
    request: Request,
    exc: CannotSaveOwnDeckError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def training_session_not_found_handler(
    request: Request,
    exc: TrainingSessionNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def training_session_item_not_found_handler(
    request: Request,
    exc: TrainingSessionItemNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "message": str(exc),
        },
    )


async def card_already_answered_handler(
    request: Request,
    exc: CardAlreadyAnsweredError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def training_session_already_exists_handler(
    request: Request,
    exc: TrainingSessionAlreadyExistsError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def training_session_already_finished_handler(
    request: Request,
    exc: TrainingSessionAlreadyFinishedError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def training_session_not_finished_yet_handler(
    request: Request,
    exc: TrainingSessionNotFinishedYet,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": str(exc),
        },
    )


async def training_session_permission_denied_handler(
    request: Request,
    exc: TrainingSessionPermissionDeniedError,
):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "message": str(exc),
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "Internal server error",
        },
    )


async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
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


async def rate_limit_error_handler(
    request: Request,
    exc: RateLimitError,
):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "message": str(exc),
        },
    )


def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(InvalidLoginCredentials, invalid_login_credentials_handler)
    app.add_exception_handler(InvalidTokenError, invalid_token_handler)
    app.add_exception_handler(InvalidRefreshTokenError, invalid_refresh_token_handler)
    app.add_exception_handler(InvalidTokenTypeError, invalid_token_type_handler)
    app.add_exception_handler(
        RefreshTokenNotFoundError,
        refresh_token_not_found_handler,
    )
    app.add_exception_handler(
        AccessTokenNotFoundError,
        access_token_not_found_handler,
    )

    app.add_exception_handler(UserNotFoundError, user_not_found_handler)
    app.add_exception_handler(UserAlreadyExistsError, user_already_exists_handler)
    app.add_exception_handler(UserPermissionDeniedError, user_permission_denied_handler)

    app.add_exception_handler(CardNotFoundError, card_not_found_handler)
    app.add_exception_handler(CardAlreadyExistsError, card_already_exists_handler)
    app.add_exception_handler(CardPermissionDeniedError, card_permission_denied_handler)

    app.add_exception_handler(DeckNotFoundError, deck_not_found_handler)
    app.add_exception_handler(DeckAlreadyExistsError, deck_already_exists_handler)
    app.add_exception_handler(DeckIsEmptyError, deck_is_empty_handler)
    app.add_exception_handler(DeckCardNotFoundError, deck_card_not_found_handler)
    app.add_exception_handler(
        InvalidDeckCardPositionError,
        invalid_deck_card_position_handler,
    )
    app.add_exception_handler(DeckCardAlreadyExistsError, deck_card_already_exists_handler)
    app.add_exception_handler(DeckPermissionDeniedError, deck_permission_denied_handler)
    app.add_exception_handler(UserDeckNotFoundError, user_deck_not_found_handler)
    app.add_exception_handler(DeckIsNotSavedError, deck_is_not_saved_handler)
    app.add_exception_handler(DeckIsNotFavouriteError, deck_is_not_favourite_handler)
    app.add_exception_handler(CannotSaveOwnDeckError, cannot_save_own_deck_handler)

    app.add_exception_handler(
        TrainingSessionNotFoundError,
        training_session_not_found_handler,
    )
    app.add_exception_handler(
        TrainingSessionAlreadyExistsError,
        training_session_already_exists_handler,
    )
    app.add_exception_handler(
            TrainingSessionAlreadyFinishedError,
            training_session_already_finished_handler,
        )
    app.add_exception_handler(
        TrainingSessionNotFinishedYet,
        training_session_not_finished_yet_handler,
    )
    app.add_exception_handler(
        TrainingSessionItemNotFoundError,
        training_session_item_not_found_handler,
    )
    app.add_exception_handler(
            CardAlreadyAnsweredError,
            card_already_answered_handler,
        )
    app.add_exception_handler(
            TrainingSessionPermissionDeniedError,
            training_session_permission_denied_handler,
        )

    app.add_exception_handler(RequestValueError, request_value_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(RateLimitError, rate_limit_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
