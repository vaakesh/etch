export const MAX_SESSION_SIZE = 500;

export type PracticeSessionScope = "all" | "50" | "100" | "custom";

export interface CustomSessionSize {
  /** Значение для запроса, `null` — поле нельзя использовать. */
  value: number | null;
  /** Поле нужно подсветить как некорректное. */
  isInvalid: boolean;
}

/** Всю колоду можно пройти за одну сессию только в пределах лимита сессии. */
export function canPracticeEntireDeck(deckWordsCount: number): boolean {
  return deckWordsCount <= MAX_SESSION_SIZE;
}

export function readCustomSessionSize(rawValue: string): CustomSessionSize {
  if (rawValue.trim() === "") {
    return { value: null, isInvalid: false };
  }

  const parsedCount = Number(rawValue);

  if (!Number.isSafeInteger(parsedCount) || parsedCount < 1) {
    return { value: null, isInvalid: true };
  }
  if (parsedCount > MAX_SESSION_SIZE) {
    return { value: MAX_SESSION_SIZE, isInvalid: true };
  }

  return { value: parsedCount, isInvalid: false };
}

/** Снижает значение до лимита сессии, остальной ввод оставляет пользователю. */
export function clampCustomSessionSize(rawValue: string): string {
  const parsedCount = Number(rawValue);

  if (!Number.isSafeInteger(parsedCount) || parsedCount <= MAX_SESSION_SIZE) {
    return rawValue;
  }

  return String(MAX_SESSION_SIZE);
}

export function getWordsPerSession(
  scope: PracticeSessionScope,
  deckWordsCount: number,
  customWordsCount: string,
): number | null {
  if (scope === "all") {
    return Math.min(Math.max(deckWordsCount, 1), MAX_SESSION_SIZE);
  }
  if (scope === "50") {
    return 50;
  }
  if (scope === "100") {
    return 100;
  }

  return readCustomSessionSize(customWordsCount).value;
}
