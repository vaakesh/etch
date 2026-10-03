import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { API_ERROR_CODES, hasApiErrorCode, isApiError } from "../../api";
import { useAuth } from "../../auth/hooks/useAuth";
import { useSessionCacheScope } from "../../auth/hooks/useSessionCacheScope";
import {
  createSessionCacheKey,
  getSessionCacheEntry,
  setSessionCacheEntry,
  type SessionCacheScope,
} from "../../auth/model/session-cache";
import { DashboardIcon } from "../../components/DashboardVisuals";
import { useAnchoredPopover } from "../../components/useAnchoredPopover";
import {
  createDeckDetailsNavigationState,
  getDeckDetailsPath,
} from "../../features/decks/model/deck-details-navigation";
import { shouldOpenDeckCreator } from "../../features/library/model/library-navigation";
import { useLongTextPreviewsEnabled } from "../../features/settings/model/useLongTextPreviewsEnabled";
import type {
  LibraryCard,
  LibraryDeckItem,
  UpdateLibraryCardInput,
} from "../../features/library/model/library-types";
import {
  LIBRARY_CARD_SEARCH_MAX_LENGTH,
  useLibraryCards,
  type UseLibraryCardsResult,
} from "../../features/library/model/useLibraryCards";
import { useLibraryDecks } from "../../features/library/model/useLibraryDecks";
import { useLibraryDeckLayout } from "../../features/library/model/useLibraryDeckLayout";
import {
  CARDS_LOADED_COUNT_FORMS,
  DECKS_LOADED_COUNT_FORMS,
  FAVOURITE_DECKS_LOADED_COUNT_FORMS,
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
  type AppLocale,
  type LocalizedCountForms,
} from "../../i18n";
import { AddCardToDeckDialog } from "./AddCardToDeckDialog";
import { ArchiveIcon } from "./ArchiveIcon";
import { CardImportDialog } from "./CardImportDialog";
import { CardEditorDialog } from "./CardEditorDialog";
import { DeckCreatorDialog } from "./DeckCreatorDialog";
import { DeckDeleteDialog } from "./DeckDeleteDialog";
import styles from "./LibraryPage.module.css";
import { OverflowingCardText } from "./OverflowingCardText";

const SAVE_COUNT_FORMS = {
  "ru-RU": { one: "сохранение", few: "сохранения", many: "сохранений", other: "сохранения" },
  "en-US": { one: "save", other: "saves" },
} satisfies LocalizedCountForms;

type LibraryActionTheme =
  | "aqua-flash"
  | "berry-burst"
  | "cherry-rush"
  | "coral-pop"
  | "lime-punch"
  | "mango-sun"
  | "mint-splash"
  | "plum-jam"
  | "tangerine-zest"
  | "violet-bloom";

// Change only this value to preview another coordinated action palette.
const LIBRARY_ACTION_THEME: LibraryActionTheme = "aqua-flash";

type LibraryStartTheme =
  | "amber-sun"
  | "aqua-capsule"
  | "berry-spark"
  | "coral-launch"
  | "graphite-neon"
  | "indigo-focus"
  | "lime-energy"
  | "mint-arrow"
  | "ruby-drive"
  | "violet-glow";

// Change only this value to preview another Start button style.
const LIBRARY_START_THEME: LibraryStartTheme = "aqua-capsule";

type LibraryDeckTitleStyle =
  "accent-rail" | "boxed-arrow" | "dotted-signal" | "gradient-underline" | "soft-pill";

// Change only this value to preview another clickable deck title style.
const LIBRARY_DECK_TITLE_STYLE: LibraryDeckTitleStyle = "gradient-underline";

const MESSAGES = defineMessages(
  {
    errors: {
      libraryGeneric: "Не удалось загрузить библиотеку. Попробуйте ещё раз.",
      libraryForbidden: "У этой учётной записи нет доступа к библиотеке.",
      libraryInvalid: "Сервер вернул данные библиотеки в неожиданном формате.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      libraryServer: "Сервер временно не может загрузить библиотеку.",
      cardsGeneric: "Не удалось загрузить карточки. Попробуйте ещё раз.",
      cardsForbidden: "У этой учётной записи нет доступа к карточкам.",
      cardsInvalid: "Сервер вернул карточки в неожиданном формате.",
      cardsServer: "Сервер временно не может загрузить карточки.",
      cardDeleteGeneric: "Не удалось удалить карточку. Попробуйте ещё раз.",
      cardDeleteForbidden: "У вас нет доступа к удалению этой карточки.",
      cardDeleteNotFound: "Карточка уже удалена или больше не существует.",
      cardDeleteServer: "Сервер временно не может удалить карточку.",
      favouriteNotFound: "Колода больше не найдена.",
      favouriteUnsaved: "Сначала сохраните колоду, чтобы добавить её в избранное.",
      favouriteGeneric: "Не удалось изменить избранное. Попробуйте ещё раз.",
      deckDeleteGeneric: "Не удалось удалить колоду. Попробуйте ещё раз.",
      deckDeleteNotFound: "Колода уже удалена или больше не существует.",
      deckDeleteServer: "Сервер временно не может удалить колоду.",
    },
    accuracy: "Точность колоды",
    correctAnswers: (value: number) => `Правильных ответов — ${value}%`,
    removeFavourite: "Удалить из избранного",
    addFavourite: "Добавить в избранное",
    saving: "Сохраняем…",
    editDeck: (title: string) => `Редактировать колоду «${title}»`,
    deckDeleting: (title: string) => `Колода «${title}» удаляется`,
    deckDeletingShort: "Колода удаляется…",
    deleteDeck: (title: string) => `Удалить колоду «${title}»`,
    deleting: "Удаляем…",
    noDescription: "Без описания",
    deckDescription: "Описание колоды",
    deckPreview: (title: string) => `Первые карточки колоды «${title}»`,
    translation: "Перевод",
    word: "Слово",
    allCardsShown: "Все карточки показаны",
    noCards: "Карточек нет",
    addFirstCard: "Добавьте первую карточку в колоду",
    lastUpdated: (value: string) => `Последнее обновление: ${value}`,
    updated: "Обновлено",
    configurePractice: (title: string) => `Настроить тренировку по колоде «${title}»`,
    startPractice: (title: string) => `Начать тренировку по колоде «${title}»`,
    openDeckPage: (title: string) => `Открыть страницу колоды «${title}»`,
    start: "Начать тренировку",
    cardActions: (text: string) => `Действия с карточкой «${text}»`,
    actions: "Действия",
    edit: "Редактировать",
    addToDeckTitle: "Добавить карточку в одну или несколько колод",
    addToDeck: "Добавить в колоду",
    deleteCardTitle: "Удалить карточку",
    delete: "Удалить",
    tabsAria: "Содержимое библиотеки",
    decks: "Колоды",
    cards: "Карточки",
    loadingDecks: "Загрузка колод",
    loadingFavourites: "Собираем любимые колоды…",
    loadingAllDecks: "Возвращаем все колоды…",
    loadingCards: "Загрузка карточек",
    retry: "Попробовать снова",
    cardsLoadErrorTitle: "Карточки не загрузились",
    cardsEmptyDescription: "Когда у вас появятся карточки, они соберутся здесь.",
    cardsEmptyTitle: "Карточек пока нет",
    loadingMore: "Загружаем…",
    showMore: "Показать ещё",
    newDeck: "Новая колода",
    newCard: "Новая карточка",
    createDeck: "Создать новую колоду",
    createCard: "Создать новую карточку",
    importCards: "Импорт",
    openImport: "Импортировать карточки из JSON",
    eyebrow: "Ваше пространство",
    title: "Библиотека",
    searchLabel: "Поиск по названию колоды",
    searchPlaceholder: "Поиск по колодам",
    cardSearchLabel: "Поиск по тексту карточек",
    cardSearchPlaceholder: "Найти слово или перевод",
    cardSearchEmptyTitle: "Карточки не найдены",
    cardSearchEmptyDescription: "Попробуйте изменить запрос или проверить написание.",
    clearCardSearch: "Очистить поиск по карточкам",
    favouritesOnly: "Только любимые",
    showArchives: "Показать архивные колоды",
    archiveLabel: "Архив колод",
    deckLayout: "Вид колод",
    fullDeckLayout: "Полный вид",
    compactDeckLayout: "Компактный вид",
    searchUnavailable: "Поиск недоступен",
    favouritesLoadError: "Любимые колоды не загрузились",
    libraryLoadError: "Библиотека не загрузилась",
    noSearchResults: "Колоды не найдены",
    emptyFavouritesDescription: "Добавьте колоды в любимые, и они появятся здесь.",
    emptyLibraryDescription: "Когда у вас появятся колоды, они соберутся здесь.",
    emptyFavouritesTitle: "Любимых колод пока нет",
    emptyLibraryTitle: "В библиотеке пока пусто",
    cardAssigned: "Карточка успешно добавлена",
  },
  {
    errors: {
      libraryGeneric: "We couldn't load the library. Try again.",
      libraryForbidden: "This account does not have access to the library.",
      libraryInvalid: "The server returned unexpected library data.",
      network: "We couldn't reach the server. Check your connection.",
      libraryServer: "The server cannot load the library right now.",
      cardsGeneric: "We couldn't load your cards. Try again.",
      cardsForbidden: "This account does not have access to the cards.",
      cardsInvalid: "The server returned unexpected card data.",
      cardsServer: "The server cannot load your cards right now.",
      cardDeleteGeneric: "We couldn't delete the card. Try again.",
      cardDeleteForbidden: "You do not have permission to delete this card.",
      cardDeleteNotFound: "This card was already deleted or no longer exists.",
      cardDeleteServer: "The server cannot delete the card right now.",
      favouriteNotFound: "This deck could not be found.",
      favouriteUnsaved: "Save the deck before adding it to favorites.",
      favouriteGeneric: "We couldn't update your favorites. Try again.",
      deckDeleteGeneric: "We couldn't delete the deck. Try again.",
      deckDeleteNotFound: "This deck was already deleted or no longer exists.",
      deckDeleteServer: "The server cannot delete the deck right now.",
    },
    accuracy: "Deck accuracy",
    correctAnswers: (value: number) => `Correct answers — ${value}%`,
    removeFavourite: "Remove from favorites",
    addFavourite: "Add to favorites",
    saving: "Saving…",
    editDeck: (title: string) => `Edit “${title}”`,
    deckDeleting: (title: string) => `Deck “${title}” is being deleted`,
    deckDeletingShort: "Deck is being deleted…",
    deleteDeck: (title: string) => `Delete “${title}”`,
    deleting: "Deleting…",
    noDescription: "No description",
    deckDescription: "Deck description",
    deckPreview: (title: string) => `First cards in “${title}”`,
    translation: "Translation",
    word: "Word",
    allCardsShown: "All cards shown",
    noCards: "No cards",
    addFirstCard: "Add the first card to this deck",
    lastUpdated: (value: string) => `Last updated: ${value}`,
    updated: "Updated",
    configurePractice: (title: string) => `Configure practice for “${title}”`,
    startPractice: (title: string) => `Start practicing “${title}”`,
    openDeckPage: (title: string) => `Open the “${title}” deck page`,
    start: "Start practice",
    cardActions: (text: string) => `Actions for card “${text}”`,
    actions: "Actions",
    edit: "Edit",
    addToDeckTitle: "Add this card to one or more decks",
    addToDeck: "Add to deck",
    deleteCardTitle: "Delete card",
    delete: "Delete",
    tabsAria: "Library content",
    decks: "Decks",
    cards: "Cards",
    loadingDecks: "Loading decks",
    loadingFavourites: "Loading favorite decks…",
    loadingAllDecks: "Loading all decks…",
    loadingCards: "Loading cards",
    retry: "Try again",
    cardsLoadErrorTitle: "Your cards didn't load",
    cardsEmptyDescription: "Your cards will appear here once you create them.",
    cardsEmptyTitle: "No cards yet",
    loadingMore: "Loading…",
    showMore: "Show more",
    newDeck: "New deck",
    newCard: "New card",
    createDeck: "Create a new deck",
    createCard: "Create a new card",
    importCards: "Import",
    openImport: "Import cards from JSON",
    eyebrow: "Your space",
    title: "Library",
    searchLabel: "Search by deck title",
    searchPlaceholder: "Search decks",
    cardSearchLabel: "Search card text",
    cardSearchPlaceholder: "Find a word or translation",
    cardSearchEmptyTitle: "No cards found",
    cardSearchEmptyDescription: "Try a different query or check the spelling.",
    clearCardSearch: "Clear card search",
    favouritesOnly: "Favorites only",
    showArchives: "Show archived decks",
    archiveLabel: "Deck archive",
    deckLayout: "Deck layout",
    fullDeckLayout: "Full view",
    compactDeckLayout: "Compact view",
    searchUnavailable: "Search is unavailable",
    favouritesLoadError: "Favorite decks didn't load",
    libraryLoadError: "The library didn't load",
    noSearchResults: "No decks found",
    emptyFavouritesDescription: "Add decks to your favorites and they will appear here.",
    emptyLibraryDescription: "Your decks will appear here once you create them.",
    emptyFavouritesTitle: "No favorite decks yet",
    emptyLibraryTitle: "Your library is empty",
    cardAssigned: "Card added successfully",
  },
);

type LibraryView = "decks" | "cards";

interface LibraryUiState {
  hasOpenedCards: boolean;
  deckSearchQuery: string;
  cardSearchQuery: string;
  scrollTop: number | null;
}

const LIBRARY_UI_CACHE_KEY = createSessionCacheKey<LibraryUiState>("library.ui");

const dateFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

function getDateFormatter(locale: AppLocale): Intl.DateTimeFormat {
  const cachedFormatter = dateFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  dateFormatters.set(locale, formatter);
  return formatter;
}

function formatUpdatedAt(value: string | null, locale: AppLocale): string | null {
  if (value === null) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : getDateFormatter(locale).format(date);
}

function getLibraryErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.libraryGeneric;
  }
  if (error.status === 403) {
    return messages.errors.libraryForbidden;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.errors.libraryInvalid;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.libraryServer;
  }

  return messages.errors.libraryGeneric;
}

function getLibraryCardsErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.cardsGeneric;
  }
  if (error.status === 403) {
    return messages.errors.cardsForbidden;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.errors.cardsInvalid;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.cardsServer;
  }

  return messages.errors.cardsGeneric;
}

function getCardDeleteErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.cardDeleteGeneric;
  }
  if (error.status === 403) {
    return messages.errors.cardDeleteForbidden;
  }
  if (error.status === 404) {
    return messages.errors.cardDeleteNotFound;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.cardDeleteServer;
  }

  return messages.errors.cardDeleteGeneric;
}

function getFavouriteErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (hasApiErrorCode(error, API_ERROR_CODES.cannotFavouriteUnsavedDeck)) {
    return messages.errors.favouriteUnsaved;
  }
  if (isApiError(error)) {
    if (error.status === 403 || error.status === 404) {
      return messages.errors.favouriteNotFound;
    }
  }

  return messages.errors.favouriteGeneric;
}

function getDeckDeleteErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.deckDeleteGeneric;
  }
  if (error.status === 403 || error.status === 404) {
    return messages.errors.deckDeleteNotFound;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.deckDeleteServer;
  }

  return messages.errors.deckDeleteGeneric;
}

function Glyph({ name }: { name: "arrow" | "delete" | "heart" | "open" | "pencil" | "sparkles" }) {
  if (name === "heart") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        viewBox="0 0 24 24"
      >
        <path d="M20.8 5.8a5.4 5.4 0 0 0-7.7 0L12 7l-1.1-1.2a5.4 5.4 0 0 0-7.7 7.7L12 22l8.8-8.5a5.4 5.4 0 0 0 0-7.7Z" />
      </svg>
    );
  }
  if (name === "pencil") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="m4 20 4.2-1 11-11a2.1 2.1 0 0 0-3-3l-11 11z" />
        <path d="m14.8 6.5 3 3M4 20l3-3" />
      </svg>
    );
  }
  if (name === "arrow") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.7"
        viewBox="0 0 24 24"
      >
        <path d="M5 12h14m-6-6 6 6-6 6" />
      </svg>
    );
  }
  if (name === "open") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M7 17 17 7M8 7h9v9" />
      </svg>
    );
  }
  if (name === "delete") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M5 7h14M9 7V4.8h6V7M7.2 7l.8 13h8l.8-13M10 11v5M14 11v5" />
      </svg>
    );
  }

  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeWidth="1.6"
      viewBox="0 0 24 24"
    >
      <path d="m12 3 1.4 4.2L18 9l-4.6 1.8L12 15l-1.4-4.2L6 9l4.6-1.8L12 3Zm7 10 .8 2.2L22 16l-2.2.8L19 19l-.8-2.2L16 16l2.2-.8L19 13ZM5 14l.9 2.6L8.5 18l-2.6 1.4L5 22l-.9-2.6L1.5 18l2.6-1.4L5 14Z" />
    </svg>
  );
}

function getAccuracyTone(
  value: number,
): "red" | "orange" | "yellow" | "green" | "turquoise" | "purple" {
  if (value >= 91) {
    return "purple";
  }
  if (value >= 81) {
    return "turquoise";
  }
  if (value >= 71) {
    return "green";
  }
  if (value >= 61) {
    return "yellow";
  }
  if (value >= 51) {
    return "orange";
  }
  return "red";
}

function AccuracyStat({ value }: { value: number }) {
  const messages = useLocalizedMessages(MESSAGES);
  const tone = getAccuracyTone(value);
  const tooltipId = useId();
  const [isTooltipOpen, setIsTooltipOpen] = useState(false);
  const hintClassName = isTooltipOpen
    ? `${styles.accuracyHint} ${styles.accuracyHintOpen}`
    : styles.accuracyHint;

  return (
    <span className={hintClassName}>
      <span
        aria-describedby={tooltipId}
        aria-label={messages.accuracy}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={value}
        aria-valuetext={`${value}%`}
        className={`${styles.accuracy} ${styles[`accuracy${tone}`]}`}
        onBlur={() => setIsTooltipOpen(false)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setIsTooltipOpen(false);
            event.currentTarget.blur();
          } else if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setIsTooltipOpen((isOpen) => !isOpen);
          }
        }}
        onPointerDown={(event) => {
          if (event.button === 0) {
            setIsTooltipOpen((isOpen) => !isOpen);
          }
        }}
        role="meter"
        tabIndex={0}
      >
        {value}
      </span>
      <span className={styles.accuracyTooltip} id={tooltipId} role="tooltip">
        <strong>{messages.accuracy}</strong>
        <span>{messages.correctAnswers(value)}</span>
      </span>
    </span>
  );
}

interface DeckCardProps {
  canEdit: boolean;
  deck: LibraryDeckItem;
  deleteError: unknown | null;
  favouriteError: unknown | null;
  isDeleting: boolean;
  isFavouriteUpdating: boolean;
  onDelete: (deckUuid: string) => void;
  onFavouriteChange: (deckUuid: string, value: boolean) => void;
  onOpenDetails: () => void;
}

function DeckCard({
  canEdit,
  deck,
  deleteError,
  favouriteError,
  isDeleting,
  isFavouriteUpdating,
  onDelete,
  onFavouriteChange,
  onOpenDetails,
}: DeckCardProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const longTextPreviewsEnabled = useLongTextPreviewsEnabled();
  const previewCards = deck.cards.slice(0, 2);
  const hasMoreCards = deck.totalWordsCount > previewCards.length;
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const updatedAtLabel = formatUpdatedAt(deck.updatedAt ?? null, locale);
  const wordCount = localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale);
  const savesCount = localizeCount(deck.savesCount, SAVE_COUNT_FORMS, locale);
  const favouriteErrorId = `favourite-error-${deck.uuid}`;
  const deleteErrorId = `delete-error-${deck.uuid}`;
  const favouriteAction = deck.isFavourite ? messages.removeFavourite : messages.addFavourite;
  const canUseManagementActions = canEdit && !isDeleting;

  return (
    <article
      className={isDeleting ? `${styles.deckCard} ${styles.deckCardDeleting}` : styles.deckCard}
      data-deck-uuid={deck.uuid}
    >
      <div className={styles.deckTopline}>
        <div className={styles.deckSignals}>
          <AccuracyStat value={deck.accuracy} />
          <span className={styles.deckSaves} title={savesCount.text}>
            <svg
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.7"
              viewBox="0 0 24 24"
            >
              <path d="M6.5 20V5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v15L12 16.5Z" />
            </svg>
            <span>{savesCount.formattedValue}</span>
            <span className={styles.visuallyHidden}> {savesCount.unit}</span>
          </span>
        </div>
        <div className={styles.deckManagement}>
          <button
            aria-describedby={favouriteError === null ? undefined : favouriteErrorId}
            aria-label={`${favouriteAction}: «${deck.title}»`}
            aria-pressed={deck.isFavourite}
            className={deck.isFavourite ? styles.favouriteActive : styles.favourite}
            disabled={isFavouriteUpdating || isDeleting}
            onClick={() => onFavouriteChange(deck.uuid, !deck.isFavourite)}
            title={isFavouriteUpdating ? messages.saving : favouriteAction}
            type="button"
          >
            <Glyph name="heart" />
          </button>
          {canEdit ? (
            <>
              {canUseManagementActions ? (
                <Link
                  aria-label={messages.editDeck(deck.title)}
                  className={styles.editButton}
                  title={messages.editDeck(deck.title)}
                  to={`/library/${deck.uuid}/edit`}
                >
                  <Glyph name="pencil" />
                </Link>
              ) : (
                <button
                  aria-label={messages.deckDeleting(deck.title)}
                  className={styles.editButton}
                  disabled
                  title={messages.deckDeletingShort}
                  type="button"
                >
                  <Glyph name="pencil" />
                </button>
              )}
              <button
                aria-describedby={deleteError === null ? undefined : deleteErrorId}
                aria-label={messages.deleteDeck(deck.title)}
                className={styles.deleteButton}
                disabled={!canUseManagementActions}
                onClick={() => setIsDeleteDialogOpen(true)}
                title={isDeleting ? messages.deleting : messages.deleteDeck(deck.title)}
                type="button"
              >
                <Glyph name="delete" />
              </button>
            </>
          ) : null}
        </div>
      </div>
      {favouriteError === null ? null : (
        <p className={styles.favouriteError} id={favouriteErrorId} role="alert">
          {getFavouriteErrorMessage(favouriteError, messages)}
        </p>
      )}
      {deleteError === null ? null : (
        <p className={styles.deckDeleteError} id={deleteErrorId} role="alert">
          {getDeckDeleteErrorMessage(deleteError, messages)}
        </p>
      )}

      <div className={styles.deckHero}>
        <div className={styles.deckCopy}>
          <h2>
            <Link
              aria-label={messages.openDeckPage(deck.title)}
              className={styles.deckDetailsLink}
              data-deck-action="open"
              onClick={onOpenDetails}
              state={createDeckDetailsNavigationState("library")}
              title={longTextPreviewsEnabled ? deck.title : messages.openDeckPage(deck.title)}
              to={getDeckDetailsPath(deck.uuid)}
            >
              <span className={styles.deckDetailsText}>{deck.title}</span>
              <Glyph name="open" />
            </Link>
          </h2>
          <OverflowingCardText
            className={styles.deckDescription}
            label={messages.deckDescription}
            text={deck.description ?? messages.noDescription}
          />
        </div>
      </div>

      <section aria-label={messages.deckPreview(deck.title)} className={styles.deckPreview}>
        {previewCards.length > 0 ? (
          <ul className={styles.previewList}>
            {previewCards.map((card) => (
              <li data-card-uuid={card.uuid} key={card.uuid}>
                <span className={styles.previewAccent} />
                <OverflowingCardText
                  className={styles.previewFront}
                  label={messages.translation}
                  language={card.frontLang}
                  text={card.frontText}
                />
                <span aria-hidden="true" className={styles.previewDivider}>
                  —
                </span>
                <OverflowingCardText
                  className={styles.previewBack}
                  label={messages.word}
                  language={card.backLang}
                  text={card.backText}
                />
              </li>
            ))}
            {previewCards.length === 1 ? (
              <li
                aria-hidden="true"
                className={
                  hasMoreCards
                    ? styles.previewPlaceholder
                    : `${styles.previewPlaceholder} ${styles.previewPlaceholderEnd}`
                }
              >
                <span>{hasMoreCards ? "•••" : messages.allCardsShown}</span>
              </li>
            ) : null}
          </ul>
        ) : (
          <div className={styles.emptyPreview} role="status">
            <strong>{messages.noCards}</strong>
            <span>{messages.addFirstCard}</span>
          </div>
        )}
        <div
          aria-hidden="true"
          className={
            previewCards.length === 2
              ? `${styles.previewContinuation} ${styles.previewContinuationVisible} ${
                  hasMoreCards ? "" : styles.previewContinuationEnd
                }`
              : styles.previewContinuation
          }
        >
          <span>{hasMoreCards ? "•••" : messages.allCardsShown}</span>
        </div>
      </section>

      <div className={styles.deckBottom}>
        <footer className={styles.deckMeta}>
          <p className={styles.deckWordCount}>{wordCount.text}</p>
          {deck.updatedAt !== null && updatedAtLabel !== null ? (
            <time
              className={styles.deckUpdatedAt}
              dateTime={deck.updatedAt}
              title={messages.lastUpdated(updatedAtLabel)}
            >
              <span className={styles.deckUpdatedLabel}>{messages.updated}</span>
              <span className={styles.deckUpdatedValue}>{updatedAtLabel}</span>
            </time>
          ) : null}
        </footer>
        <div className={styles.deckActions}>
          {isDeleting ? (
            <button
              aria-label={messages.deckDeleting(deck.title)}
              className={styles.startButton}
              disabled
              title={messages.deckDeletingShort}
              type="button"
            >
              <span>{messages.deleting}</span>
              <Glyph name="arrow" />
            </button>
          ) : (
            <Link
              aria-label={messages.configurePractice(deck.title)}
              className={styles.startButton}
              title={messages.startPractice(deck.title)}
              to={`/practice?deck=${encodeURIComponent(deck.uuid)}`}
            >
              <span>{messages.start}</span>
              <Glyph name="arrow" />
            </Link>
          )}
        </div>
      </div>
      {isDeleteDialogOpen ? (
        <DeckDeleteDialog
          deckTitle={deck.title}
          onClose={() => setIsDeleteDialogOpen(false)}
          onConfirm={() => onDelete(deck.uuid)}
        />
      ) : null}
    </article>
  );
}

type CardActionGlyphName = "add" | "delete" | "edit" | "menu";

function CardActionGlyph({ name }: { name: CardActionGlyphName }) {
  if (name === "menu") {
    return (
      <svg aria-hidden="true" fill="currentColor" viewBox="0 0 24 24">
        <circle cx="5" cy="12" r="1.7" />
        <circle cx="12" cy="12" r="1.7" />
        <circle cx="19" cy="12" r="1.7" />
      </svg>
    );
  }

  if (name === "edit") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="m4 20 4.2-1 10.9-10.9a2.2 2.2 0 0 0-3.1-3.1L5.1 15.9 4 20Z" />
        <path d="m14.7 6.3 3 3" />
      </svg>
    );
  }

  if (name === "add") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        <path d="M4.5 6.5h8.2a3 3 0 0 1 3 3v10H7.5a3 3 0 0 1-3-3v-10Z" />
        <path d="M7.5 3.5h8.2a3 3 0 0 1 3 3v7M12 10v6M9 13h6" />
      </svg>
    );
  }

  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M5 7h14M9 7V4.8h6V7M7.2 7l.8 13h8l.8-13M10 11v5M14 11v5" />
    </svg>
  );
}

interface CardActionsProps {
  card: LibraryCard;
  isDeleting: boolean;
  onAdd: () => void;
  onDelete: () => void;
  onEdit: () => void;
}

function CardActions({ card, isDeleting, onAdd, onDelete, onEdit }: CardActionsProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const menuId = useId();
  const triggerId = useId();
  const { menuRef, triggerRef, toggleMenu } = useAnchoredPopover();

  function handleEdit(): void {
    menuRef.current?.hidePopover();
    onEdit();
  }

  function handleDelete(): void {
    menuRef.current?.hidePopover();
    onDelete();
  }

  function handleAdd(): void {
    menuRef.current?.hidePopover();
    onAdd();
  }

  return (
    <div className={styles.cardActions}>
      <button
        aria-label={messages.cardActions(card.backText)}
        className={styles.cardActionsTrigger}
        id={triggerId}
        onClick={toggleMenu}
        popoverTarget={menuId}
        popoverTargetAction="toggle"
        ref={triggerRef}
        title={messages.actions}
        type="button"
      >
        <CardActionGlyph name="menu" />
      </button>
      <div
        aria-labelledby={triggerId}
        className={styles.cardActionsMenu}
        id={menuId}
        popover="auto"
        ref={menuRef}
        role="group"
      >
        <button
          className={styles.cardEditAction}
          data-card-action="edit"
          disabled={isDeleting}
          onClick={handleEdit}
          type="button"
        >
          <CardActionGlyph name="edit" />
          <span>{messages.edit}</span>
        </button>
        <button
          aria-haspopup="dialog"
          className={styles.cardAddAction}
          data-card-action="add-to-deck"
          disabled={isDeleting}
          onClick={handleAdd}
          title={messages.addToDeckTitle}
          type="button"
        >
          <CardActionGlyph name="add" />
          <span>{messages.addToDeck}</span>
        </button>
        <span aria-hidden="true" className={styles.cardActionsDivider} />
        <button
          className={styles.cardDeleteAction}
          data-card-action="delete"
          disabled={isDeleting}
          onClick={handleDelete}
          title={messages.deleteCardTitle}
          type="button"
        >
          <CardActionGlyph name="delete" />
          <span>{isDeleting ? messages.deleting : messages.delete}</span>
        </button>
      </div>
    </div>
  );
}

interface LibraryCardRowProps {
  card: LibraryCard;
  onCardAssigned?: () => void;
  onDelete: (cardUuid: string) => Promise<void>;
  onUpdate: (cardUuid: string, input: UpdateLibraryCardInput) => Promise<void>;
}

function LibraryCardRow({ card, onCardAssigned, onDelete, onUpdate }: LibraryCardRowProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const isMountedRef = useRef(true);
  const deleteInFlightRef = useRef(false);
  const [isDeckPickerOpen, setIsDeckPickerOpen] = useState(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown | null>(null);
  const cardRowClassName = isDeleting
    ? `${styles.cardRow} ${styles.cardRowDeleting}`
    : styles.cardRow;

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  async function handleDelete(): Promise<void> {
    if (deleteInFlightRef.current) {
      return;
    }

    deleteInFlightRef.current = true;
    setDeleteError(null);
    setIsDeleting(true);

    try {
      await onDelete(card.uuid);
    } catch (error: unknown) {
      if (isMountedRef.current && (!isApiError(error) || error.code !== "REQUEST_ABORTED")) {
        setDeleteError(error);
      }
    } finally {
      deleteInFlightRef.current = false;
      if (isMountedRef.current) {
        setIsDeleting(false);
      }
    }
  }

  return (
    <li aria-busy={isDeleting} className={cardRowClassName} data-card-uuid={card.uuid}>
      <div className={`${styles.cardFace} ${styles.cardFaceSource}`}>
        <span className={styles.languageBadge}>{card.backLang.toUpperCase()}</span>
        <div className={styles.cardFaceCopy}>
          <OverflowingCardText
            className={styles.cardWord}
            label={messages.word}
            language={card.backLang}
            text={card.backText}
          />
        </div>
      </div>

      <div className={`${styles.cardFace} ${styles.cardFaceTarget}`}>
        <span className={styles.languageBadge}>{card.frontLang.toUpperCase()}</span>
        <div className={styles.cardFaceCopy}>
          <OverflowingCardText
            className={styles.cardTranslation}
            label={messages.translation}
            language={card.frontLang}
            text={card.frontText}
          />
        </div>
      </div>

      <CardActions
        card={card}
        isDeleting={isDeleting}
        onAdd={() => setIsDeckPickerOpen(true)}
        onDelete={() => void handleDelete()}
        onEdit={() => setIsEditorOpen(true)}
      />
      {deleteError === null ? null : (
        <p className={styles.cardMutationError} role="alert">
          {getCardDeleteErrorMessage(deleteError, messages)}
        </p>
      )}
      {isEditorOpen ? (
        <CardEditorDialog
          card={card}
          onClose={() => setIsEditorOpen(false)}
          onSave={(input) => onUpdate(card.uuid, input)}
        />
      ) : null}
      {isDeckPickerOpen ? (
        <AddCardToDeckDialog
          card={card}
          onAssigned={onCardAssigned}
          onClose={() => setIsDeckPickerOpen(false)}
        />
      ) : null}
    </li>
  );
}

interface LibraryTabsProps {
  activeView: LibraryView;
  onChange: (view: LibraryView) => void;
}

function LibraryTabs({ activeView, onChange }: LibraryTabsProps) {
  const messages = useLocalizedMessages(MESSAGES);
  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    let nextView: LibraryView | null = null;

    if (event.key === "ArrowLeft" || event.key === "Home") {
      nextView = "decks";
    } else if (event.key === "ArrowRight" || event.key === "End") {
      nextView = "cards";
    }
    if (nextView === null) {
      return;
    }

    event.preventDefault();
    onChange(nextView);
    document.getElementById(`library-${nextView}-tab`)?.focus();
  }

  return (
    <div
      aria-label={messages.tabsAria}
      className={styles.librarySwitch}
      data-active={activeView}
      onKeyDown={handleKeyDown}
      role="tablist"
    >
      <span aria-hidden="true" className={styles.switchThumb} />
      <button
        aria-controls="library-decks-panel"
        aria-selected={activeView === "decks"}
        className={styles.switchTab}
        id="library-decks-tab"
        onClick={() => onChange("decks")}
        role="tab"
        tabIndex={activeView === "decks" ? 0 : -1}
        type="button"
      >
        {messages.decks}
      </button>
      <button
        aria-controls="library-cards-panel"
        aria-selected={activeView === "cards"}
        className={styles.switchTab}
        id="library-cards-tab"
        onClick={() => onChange("cards")}
        role="tab"
        tabIndex={activeView === "cards" ? 0 : -1}
        type="button"
      >
        {messages.cards}
      </button>
    </div>
  );
}

function DeckSkeletons() {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div aria-label={messages.loadingDecks} className={styles.decksGrid} role="status">
      {Array.from({ length: 3 }, (_, index) => (
        <div aria-hidden="true" className={styles.skeleton} key={index} />
      ))}
    </div>
  );
}

function DeckFilterLoading({ onlyFavourites }: { onlyFavourites: boolean }) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div className={styles.deckFilterLoading} role="status">
      <span aria-hidden="true" className={styles.deckFilterSpinner} />
      <span>{onlyFavourites ? messages.loadingFavourites : messages.loadingAllDecks}</span>
    </div>
  );
}

function CardSkeletons() {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div aria-label={messages.loadingCards} className={styles.cardSkeletons} role="status">
      {Array.from({ length: 3 }, (_, index) => (
        <div aria-hidden="true" className={styles.cardSkeleton} key={index} />
      ))}
    </div>
  );
}

interface StateMessageProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

function StateMessage({ title, description, actionLabel, onAction }: StateMessageProps) {
  return (
    <div className={styles.stateMessage} role={onAction ? "alert" : "status"}>
      <span aria-hidden="true" className={styles.stateMark}>
        Etch
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {actionLabel && onAction ? (
        <button onClick={onAction} type="button">
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

export function LibraryCardsPanel({
  cardLibrary,
  isSearchActive = false,
  isHidden,
  onCardAssigned,
}: {
  cardLibrary: UseLibraryCardsResult;
  isSearchActive?: boolean;
  isHidden: boolean;
  onCardAssigned?: () => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <section
      aria-labelledby="library-cards-tab"
      aria-busy={cardLibrary.status === "loading" || cardLibrary.isLoadingMore}
      className={styles.cardsPanel}
      hidden={isHidden}
      id="library-cards-panel"
      role="tabpanel"
      tabIndex={0}
    >
      {cardLibrary.status === "loading" ? <CardSkeletons /> : null}
      {cardLibrary.status === "error" ? (
        <StateMessage
          actionLabel={messages.retry}
          description={getLibraryCardsErrorMessage(cardLibrary.error, messages)}
          onAction={cardLibrary.retry}
          title={messages.cardsLoadErrorTitle}
        />
      ) : null}
      {cardLibrary.status === "success" &&
      cardLibrary.cards.length === 0 &&
      !cardLibrary.hasMore ? (
        <StateMessage
          description={
            isSearchActive ? messages.cardSearchEmptyDescription : messages.cardsEmptyDescription
          }
          title={isSearchActive ? messages.cardSearchEmptyTitle : messages.cardsEmptyTitle}
        />
      ) : null}
      {cardLibrary.status === "success" && (cardLibrary.cards.length > 0 || cardLibrary.hasMore) ? (
        <>
          <ul className={styles.cardsList}>
            {cardLibrary.cards.map((card) => (
              <LibraryCardRow
                card={card}
                key={card.uuid}
                onCardAssigned={onCardAssigned}
                onDelete={cardLibrary.deleteCard}
                onUpdate={cardLibrary.updateCard}
              />
            ))}
          </ul>
          {cardLibrary.loadMoreError ? (
            <p className={styles.loadMoreError} role="alert">
              {getLibraryCardsErrorMessage(cardLibrary.loadMoreError, messages)}
            </p>
          ) : null}
          {cardLibrary.hasMore ? (
            <button
              className={styles.loadMoreButton}
              disabled={cardLibrary.isLoadingMore}
              onClick={cardLibrary.loadMore}
              type="button"
            >
              <span>{cardLibrary.isLoadingMore ? messages.loadingMore : messages.showMore}</span>
              <DashboardIcon name="chevron" />
            </button>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

export function LibraryCreateButton({
  activeView,
  onCreateCard,
  onCreateDeck,
}: {
  activeView: LibraryView;
  onCreateCard: () => void;
  onCreateDeck: () => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const label = activeView === "decks" ? messages.newDeck : messages.newCard;
  const isDeckView = activeView === "decks";

  return (
    <button
      className={styles.newDeckButton}
      onClick={isDeckView ? onCreateDeck : onCreateCard}
      title={isDeckView ? messages.createDeck : messages.createCard}
      type="button"
    >
      <DashboardIcon name="plus" />
      <span>{label}</span>
    </button>
  );
}

function LibraryImportGlyph() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M12 3v12M7.5 10.5 12 15l4.5-4.5" />
      <path d="M5 16.5V21h14v-4.5" />
    </svg>
  );
}

export function LibraryImportButton({ onImport }: { onImport: () => void }) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <button
      className={styles.importCardsButton}
      onClick={onImport}
      title={messages.openImport}
      type="button"
    >
      <LibraryImportGlyph />
      <span>{messages.importCards}</span>
    </button>
  );
}

export function LibraryPage() {
  const cacheScope = useSessionCacheScope();

  return <LibraryPageContent cacheScope={cacheScope} key={cacheScope?.key ?? "signed-out"} />;
}

function LibraryPageContent({ cacheScope }: { cacheScope: SessionCacheScope | null }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const currentUserUuid = user?.uuid ?? null;
  const { deckLayout, changeDeckLayout } = useLibraryDeckLayout();
  const openDeckCreatorFromNavigation = shouldOpenDeckCreator(location.state);
  const cachedUiStateAtMount = getSessionCacheEntry(cacheScope, LIBRARY_UI_CACHE_KEY) ?? null;
  const activeView: LibraryView = location.pathname === "/library/cards" ? "cards" : "decks";
  const [hasOpenedCards, setHasOpenedCards] = useState(
    cachedUiStateAtMount?.hasOpenedCards ?? activeView === "cards",
  );
  const cardsOpened = hasOpenedCards || activeView === "cards";
  const [isCreateCardOpen, setIsCreateCardOpen] = useState(false);
  const [isCreateDeckOpen, setIsCreateDeckOpen] = useState(openDeckCreatorFromNavigation);
  const [isCardImportOpen, setIsCardImportOpen] = useState(false);
  const [useCompactDeckLoading, setUseCompactDeckLoading] = useState(false);
  const [deckSearchQuery, setDeckSearchQuery] = useState(
    cachedUiStateAtMount?.deckSearchQuery ?? "",
  );
  const [cardSearchQuery, setCardSearchQuery] = useState(
    cachedUiStateAtMount?.cardSearchQuery ?? "",
  );
  const [cardAssignedNoticeKey, setCardAssignedNoticeKey] = useState<number | null>(null);
  const pageRef = useRef<HTMLElement | null>(null);
  const restoreScrollTopRef = useRef(cachedUiStateAtMount?.scrollTop ?? null);
  const cardSearchInputRef = useRef<HTMLInputElement | null>(null);
  const cardAssignedNoticeSequenceRef = useRef(0);
  const cardAssignedNoticeTimeoutRef = useRef<number | null>(null);
  const isDeckSearchActive = deckSearchQuery.trim().length > 0;
  const isCardSearchActive = cardSearchQuery.trim().length > 0;
  const library = useLibraryDecks(currentUserUuid, deckSearchQuery);
  const cardLibrary = useLibraryCards({
    enabled: cardsOpened,
    onDeleteSuccess: library.retry,
    ...(cardsOpened ? { searchQuery: cardSearchQuery } : {}),
  });
  const loadedDeckCount = localizeCount(
    library.decks.length,
    !isDeckSearchActive && library.onlyFavourites
      ? FAVOURITE_DECKS_LOADED_COUNT_FORMS
      : DECKS_LOADED_COUNT_FORMS,
    locale,
  );
  const loadedCardCount = localizeCount(cardLibrary.cards.length, CARDS_LOADED_COUNT_FORMS, locale);
  const importDecks = library.decks.filter((deck) => deck.ownerUuid === currentUserUuid);

  useLayoutEffect(() => {
    const scrollTop = restoreScrollTopRef.current;
    if (scrollTop === null || library.status !== "success" || pageRef.current === null) {
      return;
    }

    pageRef.current.scrollTop = scrollTop;
    restoreScrollTopRef.current = null;
    const cachedLibraryUiState = getSessionCacheEntry(cacheScope, LIBRARY_UI_CACHE_KEY);
    if (cachedLibraryUiState !== undefined) {
      setSessionCacheEntry(cacheScope, LIBRARY_UI_CACHE_KEY, {
        ...cachedLibraryUiState,
        scrollTop: null,
      });
    }
  }, [cacheScope, library.status]);

  useEffect(() => {
    const isLegacyLibraryPath = location.pathname === "/library";
    if (!isLegacyLibraryPath && !openDeckCreatorFromNavigation) {
      return;
    }

    void navigate(
      {
        pathname: isLegacyLibraryPath ? "/library/decks" : location.pathname,
        search: location.search,
        hash: location.hash,
      },
      { replace: true, state: isLegacyLibraryPath ? location.state : null },
    );
  }, [
    location.hash,
    location.pathname,
    location.search,
    location.state,
    navigate,
    openDeckCreatorFromNavigation,
  ]);

  useEffect(
    () => () => {
      if (cardAssignedNoticeTimeoutRef.current !== null) {
        window.clearTimeout(cardAssignedNoticeTimeoutRef.current);
      }
    },
    [],
  );

  function handleViewChange(view: LibraryView): void {
    const nextHasOpenedCards = cardsOpened || view === "cards";
    setSessionCacheEntry(cacheScope, LIBRARY_UI_CACHE_KEY, {
      hasOpenedCards: nextHasOpenedCards,
      deckSearchQuery,
      cardSearchQuery,
      scrollTop: null,
    });
    setHasOpenedCards(nextHasOpenedCards);
    if (location.pathname !== `/library/${view}`) {
      void navigate(`/library/${view}`);
    }
  }

  function captureLibraryUiState(): void {
    setSessionCacheEntry(cacheScope, LIBRARY_UI_CACHE_KEY, {
      hasOpenedCards: cardsOpened,
      deckSearchQuery,
      cardSearchQuery,
      scrollTop: pageRef.current?.scrollTop ?? 0,
    });
  }

  function handleCardAssigned(): void {
    library.retry();
    cardAssignedNoticeSequenceRef.current += 1;
    setCardAssignedNoticeKey(cardAssignedNoticeSequenceRef.current);

    if (cardAssignedNoticeTimeoutRef.current !== null) {
      window.clearTimeout(cardAssignedNoticeTimeoutRef.current);
    }
    cardAssignedNoticeTimeoutRef.current = window.setTimeout(() => {
      setCardAssignedNoticeKey(null);
      cardAssignedNoticeTimeoutRef.current = null;
    }, 3200);
  }

  return (
    <main
      className={styles.page}
      data-action-theme={LIBRARY_ACTION_THEME}
      data-deck-title-style={LIBRARY_DECK_TITLE_STYLE}
      data-start-theme={LIBRARY_START_THEME}
      ref={pageRef}
    >
      <section className={styles.library}>
        <header className={styles.libraryHeader}>
          <div>
            <span className={styles.eyebrow}>{messages.eyebrow}</span>
            <h1>{messages.title}</h1>
          </div>
          <div
            className={
              activeView === "decks"
                ? `${styles.libraryHeaderActions} ${styles.libraryHeaderActionsWithImport}`
                : styles.libraryHeaderActions
            }
          >
            {activeView === "decks" ? (
              <>
                <Link
                  aria-label={messages.showArchives}
                  className={styles.archiveAction}
                  onClick={captureLibraryUiState}
                  to="/library/decks/archive"
                >
                  <ArchiveIcon />
                  <span>{messages.archiveLabel}</span>
                </Link>
                <LibraryImportButton onImport={() => setIsCardImportOpen(true)} />
              </>
            ) : null}
            <LibraryCreateButton
              activeView={activeView}
              onCreateCard={() => setIsCreateCardOpen(true)}
              onCreateDeck={() => setIsCreateDeckOpen(true)}
            />
          </div>
        </header>

        <div className={styles.toolbar}>
          <LibraryTabs activeView={activeView} onChange={handleViewChange} />
          {activeView === "decks" ? (
            <div className={`${styles.toolbarDetails} ${styles.decksToolbarDetails}`}>
              <label className={styles.deckSearchField}>
                <span className={styles.visuallyHidden}>{messages.searchLabel}</span>
                <input
                  autoComplete="off"
                  maxLength={150}
                  name="deck_search"
                  onChange={(event) => {
                    setDeckSearchQuery(event.currentTarget.value);
                  }}
                  placeholder={messages.searchPlaceholder}
                  type="search"
                  value={deckSearchQuery}
                />
              </label>
              <button
                aria-controls="library-decks-panel"
                aria-pressed={library.onlyFavourites}
                className={
                  library.onlyFavourites ? styles.favouritesFilterActive : styles.favouritesFilter
                }
                disabled={library.status === "loading"}
                onClick={() => {
                  setUseCompactDeckLoading(true);
                  library.setOnlyFavourites(!library.onlyFavourites);
                }}
                type="button"
              >
                <Glyph name="heart" />
                <span>{messages.favouritesOnly}</span>
              </button>
              {library.status === "success" ? (
                <div aria-live="polite" className={styles.summary}>
                  <Glyph name="sparkles" />
                  <span>
                    <strong>{loadedDeckCount.formattedValue}</strong> {loadedDeckCount.unit}
                  </span>
                </div>
              ) : null}
              <div
                aria-label={messages.deckLayout}
                className={styles.deckLayoutSwitch}
                role="group"
              >
                <button
                  aria-controls="library-decks-panel"
                  aria-label={messages.fullDeckLayout}
                  aria-pressed={deckLayout === "full"}
                  onClick={() => changeDeckLayout("full")}
                  title={messages.fullDeckLayout}
                  type="button"
                >
                  <svg
                    aria-hidden="true"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    viewBox="0 0 24 24"
                  >
                    <rect x="3.5" y="3.5" width="6" height="6" rx="1.5" />
                    <rect x="14.5" y="3.5" width="6" height="6" rx="1.5" />
                    <rect x="3.5" y="14.5" width="6" height="6" rx="1.5" />
                    <rect x="14.5" y="14.5" width="6" height="6" rx="1.5" />
                  </svg>
                </button>
                <button
                  aria-controls="library-decks-panel"
                  aria-label={messages.compactDeckLayout}
                  aria-pressed={deckLayout === "compact"}
                  onClick={() => changeDeckLayout("compact")}
                  title={messages.compactDeckLayout}
                  type="button"
                >
                  <svg
                    aria-hidden="true"
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeWidth="1.7"
                    viewBox="0 0 24 24"
                  >
                    <path d="M8 5h12M8 12h12M8 19h12M3.5 5H4M3.5 12H4M3.5 19H4" />
                  </svg>
                </button>
              </div>
            </div>
          ) : (
            <div className={`${styles.toolbarDetails} ${styles.cardsToolbarDetails}`}>
              <div className={styles.cardSearchField}>
                <label>
                  <span className={styles.visuallyHidden}>{messages.cardSearchLabel}</span>
                  <svg
                    aria-hidden="true"
                    className={styles.cardSearchIcon}
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeWidth="1.8"
                    viewBox="0 0 24 24"
                  >
                    <circle cx="10.8" cy="10.8" r="6.7" />
                    <path d="m16 16 4.2 4.2" />
                  </svg>
                  <input
                    aria-controls="library-cards-panel"
                    autoComplete="off"
                    maxLength={LIBRARY_CARD_SEARCH_MAX_LENGTH}
                    name="card_search"
                    onChange={(event) => {
                      setCardSearchQuery(event.currentTarget.value);
                    }}
                    placeholder={messages.cardSearchPlaceholder}
                    ref={cardSearchInputRef}
                    type="search"
                    value={cardSearchQuery}
                  />
                </label>
                {cardSearchQuery.length > 0 ? (
                  <button
                    aria-label={messages.clearCardSearch}
                    className={styles.cardSearchClear}
                    onClick={() => {
                      setCardSearchQuery("");
                      cardSearchInputRef.current?.focus();
                    }}
                    type="button"
                  >
                    <svg
                      aria-hidden="true"
                      fill="none"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeWidth="1.8"
                      viewBox="0 0 24 24"
                    >
                      <path d="m7.5 7.5 9 9m0-9-9 9" />
                    </svg>
                  </button>
                ) : null}
              </div>
              {cardLibrary.status === "success" ? (
                <div aria-live="polite" className={styles.cardsSummary}>
                  <Glyph name="sparkles" />
                  <span>
                    <strong>{loadedCardCount.formattedValue}</strong> {loadedCardCount.unit}
                  </span>
                </div>
              ) : null}
            </div>
          )}
        </div>

        <section
          aria-labelledby="library-decks-tab"
          aria-busy={library.status === "loading" || library.isLoadingMore}
          className={styles.libraryPanel}
          data-deck-layout={deckLayout}
          hidden={activeView !== "decks"}
          id="library-decks-panel"
          role="tabpanel"
        >
          {library.status === "loading" ? (
            useCompactDeckLoading && !isDeckSearchActive ? (
              <DeckFilterLoading onlyFavourites={library.onlyFavourites} />
            ) : (
              <DeckSkeletons />
            )
          ) : null}
          {library.status === "error" ? (
            <StateMessage
              actionLabel={messages.retry}
              description={getLibraryErrorMessage(library.error, messages)}
              onAction={library.retry}
              title={
                isDeckSearchActive
                  ? messages.searchUnavailable
                  : library.onlyFavourites
                    ? messages.favouritesLoadError
                    : messages.libraryLoadError
              }
            />
          ) : null}
          {isDeckSearchActive &&
          library.status === "success" &&
          library.decks.length === 0 &&
          !library.hasMore ? (
            <p className={styles.deckSearchEmpty} role="status">
              {messages.noSearchResults}
            </p>
          ) : null}
          {!isDeckSearchActive &&
          library.status === "success" &&
          library.decks.length === 0 &&
          !library.hasMore ? (
            <StateMessage
              description={
                library.onlyFavourites
                  ? messages.emptyFavouritesDescription
                  : messages.emptyLibraryDescription
              }
              title={
                library.onlyFavourites ? messages.emptyFavouritesTitle : messages.emptyLibraryTitle
              }
            />
          ) : null}
          {library.status === "success" && (library.decks.length > 0 || library.hasMore) ? (
            <>
              <div className={styles.decksGrid}>
                {library.decks.map((deck) => (
                  <DeckCard
                    canEdit={deck.ownerUuid === user?.uuid}
                    deck={deck}
                    deleteError={library.deleteErrors[deck.uuid] ?? null}
                    favouriteError={library.favouriteErrors[deck.uuid] ?? null}
                    isDeleting={library.deletingDeckUuids.includes(deck.uuid)}
                    isFavouriteUpdating={library.favouriteUpdatingDeckUuids.includes(deck.uuid)}
                    key={deck.uuid}
                    onDelete={library.deleteDeck}
                    onFavouriteChange={library.setFavourite}
                    onOpenDetails={captureLibraryUiState}
                  />
                ))}
              </div>
              {library.loadMoreError ? (
                <p className={styles.loadMoreError} role="alert">
                  {getLibraryErrorMessage(library.loadMoreError, messages)}
                </p>
              ) : null}
              {library.hasMore ? (
                <button
                  className={styles.loadMoreButton}
                  disabled={library.isLoadingMore}
                  onClick={library.loadMore}
                  type="button"
                >
                  <span>{library.isLoadingMore ? messages.loadingMore : messages.showMore}</span>
                  <DashboardIcon name="chevron" />
                </button>
              ) : null}
            </>
          ) : null}
        </section>

        {cardsOpened ? (
          <LibraryCardsPanel
            cardLibrary={cardLibrary}
            isSearchActive={isCardSearchActive}
            isHidden={activeView !== "cards"}
            onCardAssigned={handleCardAssigned}
          />
        ) : (
          <section
            aria-labelledby="library-cards-tab"
            className={styles.cardsPanel}
            hidden
            id="library-cards-panel"
            role="tabpanel"
            tabIndex={0}
          />
        )}
        {isCreateCardOpen ? (
          <CardEditorDialog
            card={null}
            onClose={() => setIsCreateCardOpen(false)}
            onSave={cardLibrary.createCard}
          />
        ) : null}
        {isCreateDeckOpen ? (
          <DeckCreatorDialog
            onClose={() => setIsCreateDeckOpen(false)}
            onSave={library.createDeck}
          />
        ) : null}
        {isCardImportOpen ? (
          <CardImportDialog
            decks={importDecks}
            onClose={() => setIsCardImportOpen(false)}
            onImport={library.importCards}
          />
        ) : null}
      </section>
      {cardAssignedNoticeKey === null ? null : (
        <div
          aria-atomic="true"
          aria-live="polite"
          className={styles.cardAssignedToast}
          key={cardAssignedNoticeKey}
          role="status"
        >
          <span aria-hidden="true" className={styles.cardAssignedToastIcon}>
            ✓
          </span>
          <span>{messages.cardAssigned}</span>
        </div>
      )}
    </main>
  );
}

export default LibraryPage;
