from typing import Protocol


class AnswerCounts(Protocol):
    @property
    def correct_count(self) -> int: ...

    @property
    def wrong_count(self) -> int: ...


def calculate_accuracy(user_deck: AnswerCounts | None) -> int:
    if (user_deck is None) or (user_deck.correct_count + user_deck.wrong_count == 0):
        return 0

    accuracy = int(
        user_deck.correct_count / (user_deck.correct_count + user_deck.wrong_count) * 100
    )
    return accuracy


def make_user_deck_identity(user_id: int, deck_id: int) -> tuple[int, int]:
    return (user_id, deck_id)
