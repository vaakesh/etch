from asyncpg.exceptions import UniqueViolationError
from sqlalchemy.exc import IntegrityError


class EmailAlreadyExistsError(Exception):
    def __init__(self, message: str = "Email is already in use"):
        super().__init__(message)


class UsernameAlreadyExistsError(Exception):
    def __init__(self, message: str = "Username is already in use"):
        super().__init__(message)


def get_unique_constraint_name(
    exc: IntegrityError,
) -> str | None:
    cause = getattr(exc.orig, "__cause__", None)

    if not isinstance(cause, UniqueViolationError):
        return None

    return cause.constraint_name

USER_EXPECTED_CONSTRAINT_ERRORS: dict[
    str,
    type[Exception],
] = {
    "uq_users_email": EmailAlreadyExistsError,
    "uq_users_username_lower": UsernameAlreadyExistsError,
}

def translate_user_integrity_error(
    exc: IntegrityError,
) -> Exception | None:
    constraint = get_unique_constraint_name(exc)

    error_type = USER_EXPECTED_CONSTRAINT_ERRORS.get(
        constraint
    )

    return error_type() if error_type is not None else None

class UserNotFoundError(Exception):
    def __init__(self, message: str = "User not found"):
        super().__init__(message)

class UserAlreadyExistsError(Exception):
    def __init__(self, message: str = "Username or email is already in use"):
        super().__init__(message)

class PermissionDeniedError(Exception):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)
