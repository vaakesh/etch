import { isApiError } from "./api-error";

/**
 * Стабильные коды ошибок backend из `app/exception_handlers.py`.
 * Один HTTP-статус несут разные ошибки, поэтому предметные случаи различают
 * по коду, а не по статусу и не по тексту `message`.
 */
export const API_ERROR_CODES = {
  invalidLoginCredentials: "INVALID_LOGIN_CREDENTIALS",
  invalidToken: "INVALID_TOKEN",
  invalidTokenType: "INVALID_TOKEN_TYPE",
  invalidRefreshToken: "INVALID_REFRESH_TOKEN",
  refreshTokenNotFound: "REFRESH_TOKEN_NOT_FOUND",
  accessTokenNotFound: "ACCESS_TOKEN_NOT_FOUND",
  captchaInvalid: "CAPTCHA_INVALID",

  userNotFound: "USER_NOT_FOUND",
  userAlreadyExists: "USER_ALREADY_EXISTS",
  userPermissionDenied: "USER_PERMISSION_DENIED",

  cardNotFound: "CARD_NOT_FOUND",
  cardAlreadyExists: "CARD_ALREADY_EXISTS",
  cardPermissionDenied: "CARD_PERMISSION_DENIED",

  deckNotFound: "DECK_NOT_FOUND",
  deckAlreadyExists: "DECK_ALREADY_EXISTS",
  deckIsEmpty: "DECK_IS_EMPTY",
  deckCardNotFound: "DECK_CARD_NOT_FOUND",
  invalidDeckCardPosition: "INVALID_DECK_CARD_POSITION",
  deckCardAlreadyExists: "DECK_CARD_ALREADY_EXISTS",
  deckSizeLimitExceeded: "DECK_SIZE_LIMIT_EXCEEDED",
  deckPermissionDenied: "DECK_PERMISSION_DENIED",
  userDeckNotFound: "USER_DECK_NOT_FOUND",
  deckIsNotSaved: "DECK_IS_NOT_SAVED",
  cannotFavouriteUnsavedDeck: "CANNOT_FAVOURITE_UNSAVED_DECK",
  deckIsNotFavourite: "DECK_IS_NOT_FAVOURITE",
  cannotSaveOwnDeck: "CANNOT_SAVE_OWN_DECK",

  trainingSessionNotFound: "TRAINING_SESSION_NOT_FOUND",
  trainingSessionItemNotFound: "TRAINING_SESSION_ITEM_NOT_FOUND",
  cardAlreadyAnswered: "CARD_ALREADY_ANSWERED",
  trainingSessionAlreadyExists: "TRAINING_SESSION_ALREADY_EXISTS",
  trainingSessionAlreadyFinished: "TRAINING_SESSION_ALREADY_FINISHED",
  trainingSessionNotFinished: "TRAINING_SESSION_NOT_FINISHED",
  trainingSessionPermissionDenied: "TRAINING_SESSION_PERMISSION_DENIED",

  rateLimitExceeded: "RATE_LIMIT_EXCEEDED",
  validationError: "VALIDATION_ERROR",
  internalServerError: "INTERNAL_SERVER_ERROR",
} as const;

export type ApiErrorCode = (typeof API_ERROR_CODES)[keyof typeof API_ERROR_CODES];

export function hasApiErrorCode(error: unknown, code: ApiErrorCode): boolean {
  return isApiError(error) && error.code === code;
}

export function hasAnyApiErrorCode(error: unknown, codes: readonly ApiErrorCode[]): boolean {
  return isApiError(error) && codes.some((code) => error.code === code);
}
