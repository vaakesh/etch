from typing import Callable
from uuid import UUID

from app.service import UnitOfWork
from app.bff.home.schemas import DeckDashboard, HomeDashboard, UserProgress
from app.decks.models import UserDeck


def calculate_accuracy(user_deck: UserDeck) -> int:
    if user_deck is None:
        return 100
    
    accuracy = int(user_deck.correct_count / (user_deck.correct_count + user_deck.wrong_count) * 100)
    return accuracy


class BffService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_home_dashboard(self, user_id: int) -> HomeDashboard:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_id(user_id=user_id)
            decks = await uow.deck_repo.get_all_by_user_id(
                user_id=user.id,
                limit=6,
            )
            user_decks = await uow.deck_repo.get_user_statistics_by_decks(
                deck_ids=[deck.id for deck in decks],
                user_id=user.id,
            )

            user_decks_by_deck_id = {
                user_deck.deck_id: user_deck
                for user_deck in user_decks
            }
            user_weekly_activity = [
                { "date": "2026-07-12", "percent": 55 },
                { "date": "2026-07-13", "percent": 67 },
                { "date": "2026-07-14", "percent": 32 },
                { "date": "2026-07-15", "percent": 12 },
                { "date": "2026-07-16", "percent": 0 },
                { "date": "2026-07-17", "percent": 38 },
                { "date": "2026-07-18", "percent": 100 }
            ]
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
                user_weekly_activity=user_weekly_activity,
            )
            return result
    
