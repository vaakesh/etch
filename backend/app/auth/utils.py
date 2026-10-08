import asyncio

from argon2 import PasswordHasher
from app.tracing import traced
from argon2.exceptions import VerifyMismatchError, InvalidHashError

ph = PasswordHasher()

# Each Argon2 run takes 64 MiB and 4 threads, so concurrent runs are capped.
PASSWORD_HASH_CONCURRENCY = 2
_password_hash_semaphore = asyncio.Semaphore(PASSWORD_HASH_CONCURRENCY)


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


# argon2-cffi releases the GIL inside its C code, so the worker thread can run
# on another logical CPU core truly in parallel with the event loop thread.
async def hash_password_async(password: str) -> str:
    async with _password_hash_semaphore:
        return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, password_hash: str) -> bool:
    async with _password_hash_semaphore:
        return await asyncio.to_thread(verify_password, password, password_hash)
