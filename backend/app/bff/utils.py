
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
