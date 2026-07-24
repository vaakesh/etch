from datetime import datetime
import base64
import json

from app.decks.models import UserDeck


def calculate_accuracy(user_deck: UserDeck) -> int:
    if (user_deck is None) or (user_deck.correct_count + user_deck.wrong_count == 0):
        return 0

    accuracy = int(user_deck.correct_count / (user_deck.correct_count + user_deck.wrong_count) * 100)
    return accuracy

def encode_cursor(updated_at: datetime, entity_id: int) -> str:
    payload = {
        "updated_at": updated_at.isoformat(),
        "id": entity_id,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()

def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        payload = json.loads(raw)

        updated_at = datetime.fromisoformat(payload["updated_at"])
        entity_id = int(payload["id"])

        if updated_at.tzinfo is None:
            raise ValueError("Cursor datetime must include timezone")

        if entity_id <= 0:
            raise ValueError("Cursor id must be positive")

        return updated_at, entity_id
    except Exception:
        raise