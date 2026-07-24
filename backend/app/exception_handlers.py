from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth.errors import (
    AccessTokenNotFoundError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    InvalidTokenTypeError,
    RefreshTokenNotFoundError,
)

from app.users.errors import (
    PermissionDeniedError as UserPermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)

from app.cards.errors import (
    CardAlreadyExistsError,
    CardNotFoundError,
    PermissionDeniedError as CardPermissionDeniedError,
)

from app.decks.errors import (
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckNotFoundError,
    PermissionDeniedError as DeckPermissionDeniedError,
)

from app.training_sessions.errors import (
    PermissionDeniedError as TrainingSessionPermissionDeniedError,
    TrainingSessionAlreadyExistsError,
    TrainingSessionNotFoundError,
)
from app.auth.cookies import clear_tokens_cookie


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


def register_exception_handlers(app: FastAPI):
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
    app.add_exception_handler(DeckCardNotFoundError, deck_card_not_found_handler)
    app.add_exception_handler(DeckCardAlreadyExistsError, deck_card_already_exists_handler)
    app.add_exception_handler(DeckPermissionDeniedError, deck_permission_denied_handler)

    app.add_exception_handler(
        TrainingSessionNotFoundError,
        training_session_not_found_handler,
    )
    app.add_exception_handler(
        TrainingSessionAlreadyExistsError,
        training_session_already_exists_handler,
    )
    app.add_exception_handler(
        TrainingSessionPermissionDeniedError,
        training_session_permission_denied_handler,
    )

    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)