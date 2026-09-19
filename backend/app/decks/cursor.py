import base64
from collections.abc import Callable
from datetime import datetime
import json
from typing import Any

from app.decks.schemas import LibraryCursor
from app.errors import RequestValueError


class CursorCodec[T]:
    def __init__(
        self,
        serialize: Callable[[T], dict[str, Any]],
        deserialize: Callable[[dict[str, Any]], T],
    ) -> None:
        self.serialize = serialize
        self.deserialize = deserialize

    def encode(
        self,
        value: T,
    ) -> str:
        payload = self.serialize(value)

        raw = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode()

        return base64.urlsafe_b64encode(raw).decode()

    def decode(
        self,
        cursor: str,
    ) -> T:
        try:
            raw = base64.urlsafe_b64decode(cursor.encode())
            payload = json.loads(raw)

            if not isinstance(payload, dict):
                raise ValueError("Cursor payload must be an object")

            return self.deserialize(payload)

        except RequestValueError:
            raise
        except Exception as exc:
            raise RequestValueError(
                message="Invalid cursor format",
                failed_field="cursor",
            ) from exc

def serialize_library_cursor(
    cursor: LibraryCursor,
) -> dict[str, Any]:
    return {
        "last_studied_at": (
            cursor.last_studied_at.isoformat()
            if cursor.last_studied_at is not None 
            else None
        ),
        "added_at": cursor.added_at.isoformat(),
        "id": cursor.id,
    }

def deserialize_library_cursor(
    payload: dict[str, Any],
) -> LibraryCursor:
    raw_last_studied_at = payload["last_studied_at"]
    last_studied_at = (
        datetime.fromisoformat(raw_last_studied_at)
        if raw_last_studied_at is not None
        else None
    )
    added_at = datetime.fromisoformat(payload["added_at"])
    id = int(payload["id"])

    if (
        last_studied_at is not None
        and last_studied_at.tzinfo is None
    ) or added_at.tzinfo is None:
        raise RequestValueError(
            message="Cursor datetime must include timezone",
            failed_field="cursor",
        )

    if id <= 0:
        raise RequestValueError(
            message="Cursor id must be positive",
            failed_field="cursor",
        )

    return LibraryCursor(
        last_studied_at=last_studied_at,
        added_at=added_at,
        id=id,
    )

library_cursor_codec = CursorCodec[LibraryCursor](
    serialize=serialize_library_cursor,
    deserialize=deserialize_library_cursor,
)
