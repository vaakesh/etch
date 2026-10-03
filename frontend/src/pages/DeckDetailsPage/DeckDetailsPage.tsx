import { useEffect, useId, useRef, useState, type MouseEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { isApiError } from "../../api";
import { useAuth } from "../../auth/hooks/useAuth";
import { getCatalogPaginationTokens } from "../../features/catalog/model/catalog-pagination";
import {
  getDeckDetailsProfilePath,
  getDeckDetailsReturnTarget,
} from "../../features/decks/model/deck-details-navigation";
import { DECK_DETAILS_CARD_PAGE_SIZE } from "../../features/decks/model/deck-details-pagination";
import type {
  DeckDetailsCard,
  UpdateDeckDetailsCardInput,
} from "../../features/decks/model/deck-details-types";
import {
  useDeckDetails,
  type UseDeckDetailsResult,
} from "../../features/decks/model/useDeckDetails";
import {
  CARD_COUNT_FORMS,
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
  type AppLocale,
  type LocalizedCountForms,
} from "../../i18n";
import { CardEditorDialog } from "../LibraryPage/CardEditorDialog";
import { DeckDeleteDialog } from "../LibraryPage/DeckDeleteDialog";
import styles from "./DeckDetailsPage.module.css";

const SAVE_COUNT_FORMS = {
  "ru-RU": {
    one: "сохранение",
    few: "сохранения",
    many: "сохранений",
    other: "сохранения",
  },
  "en-US": { one: "save", other: "saves" },
} satisfies LocalizedCountForms;

const MESSAGES = defineMessages(
  {
    backToLibrary: "Вернуться в библиотеку",
    backToCatalog: "Вернуться к предпросмотру",
    backToHome: "Вернуться на главную",
    backToPractice: "Вернуться к тренировкам",
    backToProfile: "Вернуться в профиль",
    eyebrow: "Колода",
    public: "Публичная",
    private: "Приватная",
    noDescription: "У этой колоды пока нет описания.",
    updated: "Обновлено",
    editDeck: "Редактировать колоду",
    deleteDeck: "Удалить колоду",
    deletingDeck: "Удаляем колоду…",
    startPractice: "Начать тренировку",
    cardsEyebrow: "Содержимое",
    cards: "Карточки",
    pageSummary: (shown: string, total: string) => `${shown} из ${total}`,
    noCardsTitle: "В этой колоде пока нет карточек",
    noCardsDescription: "Когда владелец добавит карточки, они появятся здесь.",
    loading: "Загружаем колоду",
    loadingPage: "Загружаем карточки…",
    loadErrorTitle: "Колода не загрузилась",
    pageErrorTitle: "Эта страница карточек не загрузилась",
    retry: "Попробовать снова",
    pagination: "Страницы карточек",
    previousPage: "Предыдущая страница",
    nextPage: "Следующая страница",
    goToPage: (page: number) => `Перейти на страницу ${page}`,
    currentPage: (page: number) => `Страница ${page}, текущая`,
    pageStatus: (page: number) => `Страница ${page}`,
    cardNumber: (number: number) => `Карточка ${number}`,
    editCard: (text: string) => `Редактировать карточку «${text}»`,
    deleteCard: (text: string) => `Удалить карточку «${text}»`,
    deletingCard: "Удаляем карточку…",
    deckDeleteError: "Не удалось удалить колоду. Попробуйте ещё раз.",
    cardDeleteError: "Не удалось удалить карточку. Попробуйте ещё раз.",
    errors: {
      generic: "Попробуйте ещё раз.",
      unavailable: "Колода не найдена или недоступна этой учётной записи.",
      invalid: "Сервер вернул данные колоды в неожиданном формате.",
      network: "Не удалось связаться с сервером.",
      server: "Сервер временно недоступен.",
    },
  },
  {
    backToLibrary: "Back to library",
    backToCatalog: "Back to preview",
    backToHome: "Back to home",
    backToPractice: "Back to practice",
    backToProfile: "Back to profile",
    eyebrow: "Deck",
    public: "Public",
    private: "Private",
    noDescription: "This deck does not have a description yet.",
    updated: "Updated",
    editDeck: "Edit deck",
    deleteDeck: "Delete deck",
    deletingDeck: "Deleting deck…",
    startPractice: "Start practice",
    cardsEyebrow: "Contents",
    cards: "Cards",
    pageSummary: (shown: string, total: string) => `${shown} of ${total}`,
    noCardsTitle: "This deck has no cards yet",
    noCardsDescription: "Cards will appear here when the owner adds them.",
    loading: "Loading deck",
    loadingPage: "Loading cards…",
    loadErrorTitle: "The deck didn't load",
    pageErrorTitle: "This page of cards didn't load",
    retry: "Try again",
    pagination: "Card pages",
    previousPage: "Previous page",
    nextPage: "Next page",
    goToPage: (page: number) => `Go to page ${page}`,
    currentPage: (page: number) => `Page ${page}, current`,
    pageStatus: (page: number) => `Page ${page}`,
    cardNumber: (number: number) => `Card ${number}`,
    editCard: (text: string) => `Edit card “${text}”`,
    deleteCard: (text: string) => `Delete card “${text}”`,
    deletingCard: "Deleting card…",
    deckDeleteError: "We couldn't delete the deck. Try again.",
    cardDeleteError: "We couldn't delete the card. Try again.",
    errors: {
      generic: "Try again.",
      unavailable: "The deck was not found or is unavailable to this account.",
      invalid: "The server returned unexpected deck data.",
      network: "Couldn't reach the server.",
      server: "The server is temporarily unavailable.",
    },
  },
);

const dateFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

function formatUpdatedAt(value: string | null, locale: AppLocale): string | null {
  if (value === null) {
    return null;
  }

  let formatter = dateFormatters.get(locale);
  if (formatter === undefined) {
    formatter = new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    dateFormatters.set(locale, formatter);
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : formatter.format(date);
}

function getLoadErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.generic;
  }
  if (error.status === 403 || error.status === 404 || error.status === 422) {
    return messages.errors.unavailable;
  }
  if (error.code === "INVALID_DECK_DETAILS_RESPONSE") {
    return messages.errors.invalid;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.server;
  }

  return messages.errors.generic;
}

type IconName = "arrow" | "back" | "delete" | "edit" | "lock" | "unlock";

function Icon({ name }: { name: IconName }) {
  let content;

  if (name === "back") {
    content = <path d="m14.5 5-7 7 7 7M8 12h10" />;
  } else if (name === "edit") {
    content = (
      <>
        <path d="m4 20 4.2-1 11-11a2.1 2.1 0 0 0-3-3l-11 11z" />
        <path d="m14.8 6.5 3 3M4 20l3-3" />
      </>
    );
  } else if (name === "delete") {
    content = (
      <>
        <path d="M5 7h14M9 7V4.8h6V7M7.2 7l.8 13h8l.8-13" />
        <path d="M10 11v5M14 11v5" />
      </>
    );
  } else if (name === "lock") {
    content = (
      <>
        <rect height="9" rx="2.2" width="14" x="5" y="10.5" />
        <path d="M8.2 10.5V8a3.8 3.8 0 0 1 7.6 0v2.5" />
      </>
    );
  } else if (name === "unlock") {
    content = (
      <>
        <rect height="9" rx="2.2" width="14" x="5" y="10.5" />
        <path d="M8.2 10.5V8a3.8 3.8 0 0 1 6.9-2.2" />
      </>
    );
  } else {
    content = <path d="M5 12h14m-6-6 6 6-6 6" />;
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
      {content}
    </svg>
  );
}

function usePaginationButtonCount(): number {
  const getButtonCount = (): number => {
    if (typeof window === "undefined") {
      return 7;
    }
    if (window.matchMedia("(max-width: 440px)").matches) {
      return 3;
    }
    return window.matchMedia("(max-width: 760px)").matches ? 5 : 7;
  };
  const [buttonCount, setButtonCount] = useState(getButtonCount);

  useEffect(() => {
    const narrowQuery = window.matchMedia("(max-width: 440px)");
    const compactQuery = window.matchMedia("(max-width: 760px)");
    const updateButtonCount = (): void => setButtonCount(getButtonCount());
    narrowQuery.addEventListener("change", updateButtonCount);
    compactQuery.addEventListener("change", updateButtonCount);

    return () => {
      narrowQuery.removeEventListener("change", updateButtonCount);
      compactQuery.removeEventListener("change", updateButtonCount);
    };
  }, []);

  return buttonCount;
}

function CardRow({
  canManage,
  card,
  number,
  onDelete,
  onUpdate,
}: {
  canManage: boolean;
  card: DeckDetailsCard;
  number: number;
  onDelete: (cardUuid: string) => Promise<void>;
  onUpdate: (cardUuid: string, input: UpdateDeckDetailsCardInput) => Promise<void>;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const isMountedRef = useRef(true);
  const deleteInFlightRef = useRef(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown | null>(null);

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
    <li
      aria-busy={isDeleting}
      className={isDeleting ? `${styles.card} ${styles.cardDeleting}` : styles.card}
      data-card-uuid={card.uuid}
    >
      <span aria-label={messages.cardNumber(number)} className={styles.cardNumber}>
        {number}
      </span>
      <div className={styles.cardSide}>
        <span>{card.frontLang.toUpperCase()}</span>
        <p lang={card.frontLang}>{card.frontText}</p>
      </div>
      <div className={styles.cardSide}>
        <span>{card.backLang.toUpperCase()}</span>
        <p lang={card.backLang}>{card.backText}</p>
      </div>
      {canManage ? (
        <div className={styles.cardActions}>
          <button
            aria-label={messages.editCard(card.frontText)}
            disabled={isDeleting}
            onClick={() => setIsEditorOpen(true)}
            title={messages.editCard(card.frontText)}
            type="button"
          >
            <Icon name="edit" />
          </button>
          <button
            aria-label={messages.deleteCard(card.frontText)}
            className={styles.cardDeleteButton}
            disabled={isDeleting}
            onClick={() => void handleDelete()}
            title={isDeleting ? messages.deletingCard : messages.deleteCard(card.frontText)}
            type="button"
          >
            <Icon name="delete" />
          </button>
        </div>
      ) : null}
      {deleteError === null ? null : (
        <p className={styles.cardError} role="alert">
          {messages.cardDeleteError}
        </p>
      )}
      {isEditorOpen ? (
        <CardEditorDialog
          card={card}
          onClose={() => setIsEditorOpen(false)}
          onSave={(input) => onUpdate(card.uuid, input)}
        />
      ) : null}
    </li>
  );
}

function Pagination({
  details,
  onSelect,
}: {
  details: UseDeckDetailsResult;
  onSelect: (page: number) => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const buttonCount = usePaginationButtonCount();

  if (details.pageCount <= 1) {
    return null;
  }

  return (
    <nav aria-label={messages.pagination} className={styles.pagination}>
      <span aria-live="polite" className={styles.visuallyHidden} role="status">
        {messages.pageStatus(details.currentPage)}
      </span>
      <button
        aria-label={messages.previousPage}
        className={styles.paginationArrow}
        disabled={details.currentPage === 1 || details.isPageLoading}
        onClick={() => onSelect(details.currentPage - 1)}
        type="button"
      >
        <Icon name="back" />
      </button>
      <ol className={styles.paginationList}>
        {getCatalogPaginationTokens(details.pageCount, details.currentPage, buttonCount).map(
          (token) => (
            <li key={token.key}>
              {token.type === "ellipsis" ? (
                <span aria-hidden="true" className={styles.paginationEllipsis}>
                  …
                </span>
              ) : (
                <button
                  aria-current={token.pageNumber === details.currentPage ? "page" : undefined}
                  aria-label={
                    token.pageNumber === details.currentPage
                      ? messages.currentPage(token.pageNumber)
                      : messages.goToPage(token.pageNumber)
                  }
                  className={
                    token.pageNumber === details.currentPage
                      ? `${styles.paginationButton} ${styles.paginationButtonActive}`
                      : styles.paginationButton
                  }
                  disabled={details.isPageLoading}
                  onClick={() => onSelect(token.pageNumber)}
                  type="button"
                >
                  {token.pageNumber}
                </button>
              )}
            </li>
          ),
        )}
      </ol>
      <button
        aria-label={messages.nextPage}
        className={styles.paginationArrow}
        disabled={details.currentPage === details.pageCount || details.isPageLoading}
        onClick={() => onSelect(details.currentPage + 1)}
        type="button"
      >
        <Icon name="arrow" />
      </button>
    </nav>
  );
}

export function DeckDetailsPage() {
  const { deck_uuid: deckUuid = "" } = useParams<{ deck_uuid: string }>();
  const { user } = useAuth();
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const location = useLocation();
  const navigate = useNavigate();
  const details = useDeckDetails(deckUuid);
  const cardsSectionRef = useRef<HTMLElement | null>(null);
  const cardsHeadingId = useId();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeletingDeck, setIsDeletingDeck] = useState(false);
  const [deckDeleteError, setDeckDeleteError] = useState<unknown | null>(null);
  const deck = details.deck;
  const isOwner = deck !== null && deck.ownerUuid === user?.uuid;
  const updatedAt = deck === null ? null : formatUpdatedAt(deck.updatedAt, locale);
  const wordCount = localizeCount(deck?.totalWordsCount ?? 0, WORD_COUNT_FORMS, locale);
  const saveCount = localizeCount(deck?.savesCount ?? 0, SAVE_COUNT_FORMS, locale);
  const shownCount = localizeCount(details.cards.length, CARD_COUNT_FORMS, locale);
  const returnTarget = getDeckDetailsReturnTarget(location.state);
  const profileBackPath = getDeckDetailsProfilePath(location.state);
  const backLabel =
    returnTarget === "catalog"
      ? messages.backToCatalog
      : returnTarget === "home"
        ? messages.backToHome
        : returnTarget === "practice"
          ? messages.backToPractice
          : returnTarget === "profile"
            ? messages.backToProfile
            : messages.backToLibrary;
  const backPath =
    returnTarget === "catalog"
      ? "/catalog"
      : returnTarget === "home"
        ? "/"
        : returnTarget === "practice"
          ? "/practice"
          : returnTarget === "profile" && profileBackPath !== null
            ? profileBackPath
            : "/library";

  function handleBack(event: MouseEvent<HTMLAnchorElement>): void {
    if (
      returnTarget === null ||
      event.button !== 0 ||
      event.metaKey ||
      event.altKey ||
      event.ctrlKey ||
      event.shiftKey
    ) {
      return;
    }

    event.preventDefault();
    navigate(-1);
  }

  function selectPage(page: number): void {
    if (page === details.currentPage || page < 1 || page > details.pageCount) {
      return;
    }

    details.selectPage(page);
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth";
    cardsSectionRef.current?.scrollIntoView({ behavior, block: "start" });
  }

  async function handleDeleteDeck(): Promise<void> {
    if (isDeletingDeck) {
      return;
    }

    setDeckDeleteError(null);
    setIsDeletingDeck(true);
    try {
      await details.deleteDeck();
      navigate("/library", { replace: true });
    } catch (error: unknown) {
      if (!isApiError(error) || error.code !== "REQUEST_ABORTED") {
        setDeckDeleteError(error);
      }
      setIsDeletingDeck(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        {details.status === "loading" ? (
          <div aria-label={messages.loading} className={styles.loading} role="status">
            <span />
            <span />
            <span />
          </div>
        ) : null}

        {details.status === "error" ? (
          <section className={styles.state} role="alert">
            <span aria-hidden="true" className={styles.stateMark}>
              !
            </span>
            <h1>{messages.loadErrorTitle}</h1>
            <p>{getLoadErrorMessage(details.error, messages)}</p>
            <div className={styles.stateActions}>
              <Link onClick={handleBack} to={backPath}>
                {backLabel}
              </Link>
              <button onClick={details.retry} type="button">
                {messages.retry}
              </button>
            </div>
          </section>
        ) : null}

        {details.status === "success" && deck !== null ? (
          <div className={styles.content}>
            <header className={styles.hero}>
              <div className={styles.heroTopline}>
                <Link
                  aria-label={backLabel}
                  className={styles.backLink}
                  onClick={handleBack}
                  to={backPath}
                >
                  <Icon name="back" />
                </Link>
                <div className={styles.badges}>
                  <span className={styles.ownerBadge}>@{deck.ownerUsername}</span>
                  <span className={styles.visibilityBadge}>
                    <Icon name={deck.isPublic ? "unlock" : "lock"} />
                    {deck.isPublic ? messages.public : messages.private}
                  </span>
                </div>
              </div>

              <div className={styles.heroBody}>
                <div className={styles.heroCopy}>
                  <span className={styles.eyebrow}>{messages.eyebrow}</span>
                  <h1>{deck.title}</h1>
                  <p>{deck.description ?? messages.noDescription}</p>
                </div>

                {isOwner ? (
                  <div className={styles.managementActions}>
                    <Link
                      aria-label={messages.editDeck}
                      className={styles.editButton}
                      title={messages.editDeck}
                      to={`/library/${deck.uuid}/edit`}
                    >
                      <Icon name="edit" />
                    </Link>
                    <button
                      aria-label={isDeletingDeck ? messages.deletingDeck : messages.deleteDeck}
                      className={styles.deleteButton}
                      disabled={isDeletingDeck}
                      onClick={() => setIsDeleteDialogOpen(true)}
                      title={isDeletingDeck ? messages.deletingDeck : messages.deleteDeck}
                      type="button"
                    >
                      <Icon name="delete" />
                    </button>
                  </div>
                ) : null}
              </div>

              <div className={styles.heroFooter}>
                <div className={styles.deckFacts}>
                  <dl className={styles.keyStats}>
                    <div>
                      <dt>{wordCount.unit}</dt>
                      <dd>{wordCount.formattedValue}</dd>
                    </div>
                    <div>
                      <dt>{saveCount.unit}</dt>
                      <dd>{saveCount.formattedValue}</dd>
                    </div>
                  </dl>
                  {deck.updatedAt !== null && updatedAt !== null ? (
                    <p className={styles.updatedMeta}>
                      <span>{messages.updated}</span>
                      <time dateTime={deck.updatedAt}>{updatedAt}</time>
                    </p>
                  ) : null}
                </div>

                <Link
                  className={styles.practiceButton}
                  to={`/practice?deck=${encodeURIComponent(deck.uuid)}`}
                >
                  <span>{messages.startPractice}</span>
                  <Icon name="arrow" />
                </Link>
              </div>
              {deckDeleteError === null ? null : (
                <p className={styles.deckDeleteError} role="alert">
                  {messages.deckDeleteError}
                </p>
              )}
            </header>

            <section
              aria-busy={details.isPageLoading}
              aria-labelledby={cardsHeadingId}
              className={styles.cardsSection}
              ref={cardsSectionRef}
            >
              <div className={styles.cardsHeader}>
                <div>
                  <span className={styles.eyebrow}>{messages.cardsEyebrow}</span>
                  <h2 id={cardsHeadingId}>{messages.cards}</h2>
                </div>
                {deck.totalWordsCount > 0 ? (
                  <p>{messages.pageSummary(shownCount.formattedValue, wordCount.formattedValue)}</p>
                ) : null}
              </div>

              {deck.totalWordsCount === 0 ? (
                <div className={styles.empty} role="status">
                  <span aria-hidden="true">•••</span>
                  <h3>{messages.noCardsTitle}</h3>
                  <p>{messages.noCardsDescription}</p>
                </div>
              ) : details.isPageLoading ? (
                <div className={styles.pageState} role="status">
                  <span className={styles.spinner} />
                  <p>{messages.loadingPage}</p>
                </div>
              ) : details.pageError !== null ? (
                <div className={styles.pageState} role="alert">
                  <h3>{messages.pageErrorTitle}</h3>
                  <p>{getLoadErrorMessage(details.pageError, messages)}</p>
                  <button onClick={details.retryPage} type="button">
                    {messages.retry}
                  </button>
                </div>
              ) : (
                <ol className={styles.cardList}>
                  {details.cards.map((card, index) => (
                    <CardRow
                      canManage={isOwner}
                      card={card}
                      key={card.uuid}
                      number={(details.currentPage - 1) * DECK_DETAILS_CARD_PAGE_SIZE + index + 1}
                      onDelete={details.deleteCard}
                      onUpdate={details.updateCard}
                    />
                  ))}
                </ol>
              )}

              <Pagination details={details} onSelect={selectPage} />
            </section>
          </div>
        ) : null}
      </div>

      {isDeleteDialogOpen && deck !== null ? (
        <DeckDeleteDialog
          deckTitle={deck.title}
          onClose={() => setIsDeleteDialogOpen(false)}
          onConfirm={() => void handleDeleteDeck()}
        />
      ) : null}
    </main>
  );
}

export default DeckDetailsPage;
