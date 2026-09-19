import random


def pick_random_positions(words_count: int, count: int) -> list[int] | None:
    """
    рандомные count позиций из words_count\n
    None - все позиции
    """
    if count >= words_count:
        return None
    return random.sample(range(1, words_count + 1), count)
