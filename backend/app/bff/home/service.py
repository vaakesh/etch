from typing import Callable
from uuid import UUID

from app.service import UnitOfWork
from app.bff.home.schemas import DeckDashboard, HomeDashboard, UserProgress
from app.decks.models import UserDeck


def calculate_accuracy(user_deck: UserDeck) -> int:
    if user_deck is None:
        return 0
    
    accuracy = int(user_deck.correct_count / (user_deck.correct_count + user_deck.wrong_count) * 100)
    return accuracy


class BffService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_home_dashboard(self, user_id: int) -> HomeDashboard:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_id(user_id=user_id)
            print(user)
            decks = await uow.deck_repo.get_all_by_user_id(
                user_id=user.id,
                limit=6,
            )
            print(decks)
            user_decks = await uow.deck_repo.get_user_statistics_by_decks(
                deck_ids=[deck.id for deck in decks],
                user_id=user.id,
            )

            user_decks_by_deck_id = {
                user_deck.deck_id: user_deck
                for user_deck in user_decks
            }
            print(user_decks_by_deck_id)
            result = HomeDashboard(
                decks=[DeckDashboard(
                    title=deck.title,
                    description=deck.description,
                    deck_total_words_count=deck.words_count,
                    user_accuracy=calculate_accuracy(
                        user_decks_by_deck_id.get(deck.id)
                    ),
                    updated_at=deck.updated_at,
                ) for deck in decks],
                progress=UserProgress(
                    user_words_explored=67,
                    user_weekly_accuracy=55,
                    user_current_streak=6,
                    user_total_study_time=120,
                ),
                user_weekly_activity=[55, 67, 32, 12, 0, 38, 100],
            )
            return result
    