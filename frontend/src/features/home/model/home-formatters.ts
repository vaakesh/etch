const countFormatter = new Intl.NumberFormat("ru-RU");
const percentFormatter = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 1,
});
export function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

export function formatCount(value: number): string {
  return countFormatter.format(Math.max(0, Math.trunc(value)));
}

export function formatPercent(value: number): string {
  return `${percentFormatter.format(clampPercent(value))}%`;
}

export function formatStudyTime(seconds: number): string {
  const safeSeconds = Math.max(0, Math.trunc(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);

  if (hours > 0 && minutes > 0) {
    return `${hours} ч ${minutes} мин`;
  }
  if (hours > 0) {
    return `${hours} ч`;
  }
  if (minutes > 0) {
    return `${minutes} мин`;
  }

  return `${safeSeconds} сек`;
}

export function formatStreak(days: number): string {
  const safeDays = Math.max(0, Math.trunc(days));
  const lastTwoDigits = safeDays % 100;
  const lastDigit = safeDays % 10;
  let unit = "дней";

  if (lastTwoDigits < 11 || lastTwoDigits > 14) {
    if (lastDigit === 1) {
      unit = "день";
    } else if (lastDigit >= 2 && lastDigit <= 4) {
      unit = "дня";
    }
  }

  return `${safeDays} ${unit}`;
}
