from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.fsrs.scheduler import Scheduler
from app.fsrs.types import Rating

# Один планировщик на всё приложение: пошаговое обновление в submit_answer
# и пересборка из журнала должны считать одинаково
SCHEDULER = Scheduler()


def end_of_local_day(now: datetime, timezone: str) -> datetime:
    # Начало следующих суток пользователя в UTC: граница «повторить сегодня».
    # Через combine, а не now + 1 день: в день перевода часов сутки не 24 часа
    zone = ZoneInfo(timezone)
    local_date = now.astimezone(zone).date()
    next_midnight = datetime.combine(local_date + timedelta(days=1), time(), tzinfo=zone)
    return next_midnight.astimezone(UTC)


def rating_from_answer(is_correct: bool) -> Rating:
    # Автоматическая оценка, если пользователь не оценил ответ сам.
    # Пропуск и ошибка означают «не вспомнил»
    return Rating.GOOD if is_correct else Rating.AGAIN


def effective_rating(is_correct: bool, self_rating: int | None) -> Rating:
    # Самооценка важнее автоматической: пользователь мог опечататься, хотя слово помнит
    if self_rating is not None:
        return Rating(self_rating)
    return rating_from_answer(is_correct)
