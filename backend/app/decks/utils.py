from app.decks.models import UserDeck


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

def make_user_deck_identity(user_id: int, deck_id: int) -> tuple[int, int]:
    return (user_id, deck_id)