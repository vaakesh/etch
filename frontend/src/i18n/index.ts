export { LocaleProvider } from "./LocaleProvider";
export { useLocale } from "./useLocale";
export { defineMessages } from "./messages";
export type { LocalizedMessages } from "./messages";
export { useLocalizedMessages } from "./useLocalizedMessages";
export {
  CARD_COUNT_FORMS,
  CARDS_LOADED_COUNT_FORMS,
  CORRECT_ANSWER_COUNT_FORMS,
  DAY_COUNT_FORMS,
  DECKS_LEFT_TO_SAVE_COUNT_FORMS,
  DECKS_LOADED_COUNT_FORMS,
  DEFAULT_LOCALE,
  FAVOURITE_DECKS_LOADED_COUNT_FORMS,
  HIDDEN_CARD_COUNT_FORMS,
  HOUR_SHORT_COUNT_FORMS,
  MINUTE_SHORT_COUNT_FORMS,
  SECOND_SHORT_COUNT_FORMS,
  SELECTED_DECK_COUNT_FORMS,
  SUPPORTED_LOCALES,
  WORD_COUNT_FORMS,
  WRONG_ANSWER_COUNT_FORMS,
  formatNumber,
  isSupportedLocale,
  localizeCount,
  normalizeCount,
} from "./localization";
export type {
  AppLocale,
  LocalizedCount,
  LocalizedCountForms,
  PluralCategory,
  PluralForms,
} from "./localization";
