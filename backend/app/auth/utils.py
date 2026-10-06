from argon2 import PasswordHasher
from app.tracing import traced
from argon2.exceptions import VerifyMismatchError, InvalidHashError

ph = PasswordHasher()


@traced("auth.hash_password")
def hash_password(password: str) -> str:
    return ph.hash(password)

@traced("auth.verify_password")
def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except InvalidHashError:
        raise InvalidHashError("Invalid password")
    except Exception:
        raise
