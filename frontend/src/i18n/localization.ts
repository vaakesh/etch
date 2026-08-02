export const SUPPORTED_LOCALES = ["ru-RU", "en-US"] as const;

export type AppLocale = (typeof SUPPORTED_LOCALES)[number];
export type PluralCategory = "zero" | "one" | "two" | "few" | "many" | "other";

export interface PluralForms {
  other: string;
  zero?: string;
  one?: string;
  two?: string;
  few?: string;
  many?: string;
}

export type LocalizedCountForms = Readonly<Record<AppLocale, Readonly<PluralForms>>>;

export interface LocalizedCount {
  category: PluralCategory;
  formattedValue: string;
  text: string;
  unit: string;
  value: number;
}

export const DEFAULT_LOCALE: AppLocale = "ru-RU";

const pluralRules = new Map<AppLocale, Intl.PluralRules>();
const numberFormatters = new Map<AppLocale, Intl.NumberFormat>();

function getPluralRules(locale: AppLocale): Intl.PluralRules {
  const cachedRules = pluralRules.get(locale);
  if (cachedRules !== undefined) {
    return cachedRules;
  }

  const rules = new Intl.PluralRules(locale);
  pluralRules.set(locale, rules);
  return rules;
}

function getNumberFormatter(locale: AppLocale): Intl.NumberFormat {
  const cachedFormatter = numberFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.NumberFormat(locale);
  numberFormatters.set(locale, formatter);
  return formatter;
}

export function isSupportedLocale(value: unknown): value is AppLocale {
  return typeof value === "string" && SUPPORTED_LOCALES.some((locale) => locale === value);
}

export function normalizeCount(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0;
}

export function formatNumber(value: number, locale: AppLocale = DEFAULT_LOCALE): string {
  return getNumberFormatter(locale).format(value);
}

export function localizeCount(
  value: number,
  forms: LocalizedCountForms,
  locale: AppLocale = DEFAULT_LOCALE,
): LocalizedCount {
  const normalizedValue = normalizeCount(value);
  const category = getPluralRules(locale).select(normalizedValue) as PluralCategory;
  const localeForms = forms[locale];
  const unit = localeForms[category] ?? localeForms.other;
  const formattedValue = formatNumber(normalizedValue, locale);

  return {
    category,
    formattedValue,
    text: `${formattedValue} ${unit}`,
    unit,
    value: normalizedValue,
  };
}

export const WORD_COUNT_FORMS = {
  "ru-RU": { one: "слово", few: "слова", many: "слов", other: "слова" },
  "en-US": { one: "word", other: "words" },
} satisfies LocalizedCountForms;

export const CARD_COUNT_FORMS = {
  "ru-RU": { one: "карточка", few: "карточки", many: "карточек", other: "карточки" },
  "en-US": { one: "card", other: "cards" },
} satisfies LocalizedCountForms;

export const DAY_COUNT_FORMS = {
  "ru-RU": { one: "день", few: "дня", many: "дней", other: "дня" },
  "en-US": { one: "day", other: "days" },
} satisfies LocalizedCountForms;

export const DECKS_LOADED_COUNT_FORMS = {
  "ru-RU": {
    one: "колода загружена",
    few: "колоды загружены",
    many: "колод загружено",
    other: "колоды загружены",
  },
  "en-US": { one: "deck loaded", other: "decks loaded" },
} satisfies LocalizedCountForms;

export const FAVOURITE_DECKS_LOADED_COUNT_FORMS = {
  "ru-RU": {
    one: "любимая колода загружена",
    few: "любимые колоды загружены",
    many: "любимых колод загружено",
    other: "любимые колоды загружены",
  },
  "en-US": { one: "favorite deck loaded", other: "favorite decks loaded" },
} satisfies LocalizedCountForms;

export const CARDS_LOADED_COUNT_FORMS = {
  "ru-RU": {
    one: "карточка загружена",
    few: "карточки загружены",
    many: "карточек загружено",
    other: "карточки загружены",
  },
  "en-US": { one: "card loaded", other: "cards loaded" },
} satisfies LocalizedCountForms;

export const SELECTED_DECK_COUNT_FORMS = {
  "ru-RU": {
    one: "колода выбрана",
    few: "колоды выбраны",
    many: "колод выбрано",
    other: "колоды выбраны",
  },
  "en-US": { one: "deck selected", other: "decks selected" },
} satisfies LocalizedCountForms;

export const DECKS_LEFT_TO_SAVE_COUNT_FORMS = {
  "ru-RU": {
    one: "колоду осталось сохранить",
    few: "колоды осталось сохранить",
    many: "колод осталось сохранить",
    other: "колоды осталось сохранить",
  },
  "en-US": { one: "deck left to save", other: "decks left to save" },
} satisfies LocalizedCountForms;

export const CORRECT_ANSWER_COUNT_FORMS = {
  "ru-RU": {
    one: "верный ответ",
    few: "верных ответа",
    many: "верных ответов",
    other: "верного ответа",
  },
  "en-US": { one: "correct answer", other: "correct answers" },
} satisfies LocalizedCountForms;

export const WRONG_ANSWER_COUNT_FORMS = {
  "ru-RU": {
    one: "неверный ответ",
    few: "неверных ответа",
    many: "неверных ответов",
    other: "неверного ответа",
  },
  "en-US": { one: "wrong answer", other: "wrong answers" },
} satisfies LocalizedCountForms;

export const HIDDEN_CARD_COUNT_FORMS = {
  "ru-RU": {
    one: "карточка пропущена",
    few: "карточки пропущены",
    many: "карточек пропущено",
    other: "карточки пропущены",
  },
  "en-US": { one: "card hidden", other: "cards hidden" },
} satisfies LocalizedCountForms;

export const HOUR_SHORT_COUNT_FORMS = {
  "ru-RU": { other: "ч" },
  "en-US": { other: "hr" },
} satisfies LocalizedCountForms;

export const MINUTE_SHORT_COUNT_FORMS = {
  "ru-RU": { other: "мин" },
  "en-US": { other: "min" },
} satisfies LocalizedCountForms;

export const SECOND_SHORT_COUNT_FORMS = {
  "ru-RU": { other: "сек" },
  "en-US": { other: "sec" },
} satisfies LocalizedCountForms;
