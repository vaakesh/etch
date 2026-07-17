





from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeckDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str | None = None
    deck_total_words_count: int
    user_accuracy: int
    updated_at: datetime | None = None

class UserProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_words_explored: int
    user_weekly_accuracy: float
    user_current_streak: int # days
    user_total_study_time: int # seconds

class HomeDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decks: list[DeckDashboard]
    progress: UserProgress
    user_weekly_activity: list[int] # массив процентов, которыми нужно заполнить шкалы, 100 - 100%, 55 - 55% и тд

