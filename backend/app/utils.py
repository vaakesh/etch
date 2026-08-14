import base64
import json
from datetime import UTC, datetime

from app.errors import RequestValueError
from app.decks.models import UserDeck


def utcnow() -> datetime:
    return datetime.now(UTC)

def format_duration(duration: float) -> str:
    if duration > 1.0:
        color = "\x1b[31m"
    elif duration > 0.3:
        color = "\x1b[33m"
    else:
        color = "\x1b[32m"
    reset = "\x1b[0m"
    return f"{color}{duration:.3f}s{reset}"


def encode_cursor(time_condition: datetime, entity_id: int) -> str:
    payload = {
        "time_condition": time_condition.isoformat(),
        "id": entity_id,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()

def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        payload = json.loads(raw)

        time_condition = datetime.fromisoformat(payload["time_condition"])
        entity_id = int(payload["id"])

        if time_condition.tzinfo is None:
            raise RequestValueError(
                message="Cursor datetime must include timezone",
                failed_field="cursor",
            )

        if entity_id <= 0:
            raise RequestValueError(
                message="Cursor id must be positive",
                failed_field="cursor",
            )

        return time_condition, entity_id
    except RequestValueError:
        raise
    except Exception as exc:
        raise RequestValueError(
            message="Invalid cursor format",
            failed_field="cursor",
        ) from exc

def calculate_accuracy(user_deck: UserDeck) -> int:
    if (user_deck is None) or (user_deck.correct_count + user_deck.wrong_count == 0):
        return 0

    accuracy = (
        int
        (
            user_deck.correct_count / 
            (user_deck.correct_count + user_deck.wrong_count)
            * 100
        )
    )
    return accuracy