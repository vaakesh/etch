from app.decks.models import UserDeck


def make_user_deck_identity(user_id: int, deck_id: int) -> tuple[int, int]:
    return (user_id, deck_id)