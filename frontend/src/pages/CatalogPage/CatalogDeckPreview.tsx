import { useEffect, useId, useRef, useState, type SyntheticEvent } from "react";
import { Link } from "react-router-dom";
import { isApiError } from "../../api";
import { formatCatalogUpdatedAt } from "../../features/catalog/model/catalog-formatters";
import { getCatalogPaginationTokens } from "../../features/catalog/model/catalog-pagination";
import { CATALOG_PREVIEW_CARD_PAGE_SIZE } from "../../features/catalog/model/catalog-preview-pagination";
import { useCatalogDeckPreview } from "../../features/catalog/model/useCatalogDeckPreview";
import {
  createDeckDetailsNavigationState,
  getDeckDetailsPath,
  type DeckDetailsReturnTarget,
} from "../../features/decks/model/deck-details-navigation";
import {
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
  type LocalizedCountForms,
} from "../../i18n";
import styles from "./CatalogPage.module.css";

const PREVIEW_SAVE_COUNT_FORMS = {
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
    dialogLabel: "Предпросмотр колоды",
    close: "Закрыть",
    openDeck: "Открыть колоду",
    openDeckPage: "Открыть страницу колоды",
    owner: (username: string) => `Автор: @${username}`,
    updated: "Обновлено",
    noDescription: "Без описания",
    cards: "Карточки",
    noCards: "В этой колоде пока нет карточек",
    loading: "Загружаем предпросмотр…",
    errorTitle: "Предпросмотр не загрузился",
    retry: "Попробовать снова",
    loadingPage: "Загружаем карточки…",
    pageError: "Не удалось загрузить эту страницу карточек.",
    pagination: "Страницы карточек",
    previousPage: "Предыдущая страница",
    nextPage: "Следующая страница",
    goToPage: (page: number) => `Перейти на страницу ${page}`,
    currentPage: (page: number) => `Страница ${page}, текущая`,
    pageStatus: (page: number) => `Страница ${page}`,
    errors: {
      generic: "Попробуйте ещё раз.",
      forbidden: "У этой учётной записи нет доступа к колоде.",
      notFound: "Колода больше недоступна.",
      invalid: "Сервер вернул данные в неожиданном формате.",
      network: "Не удалось связаться с сервером.",
      server: "Сервер временно недоступен.",
    },
  },
  {
    dialogLabel: "Deck preview",
    close: "Close",
    openDeck: "Open deck",
    openDeckPage: "Open deck page",
    owner: (username: string) => `Author: @${username}`,
    updated: "Updated",
    noDescription: "No description",
    cards: "Cards",
    noCards: "This deck has no cards yet",
    loading: "Loading preview…",
    errorTitle: "Preview didn't load",
    retry: "Try again",
    loadingPage: "Loading cards…",
    pageError: "Couldn't load this page of cards.",
    pagination: "Card pages",
    previousPage: "Previous page",
    nextPage: "Next page",
    goToPage: (page: number) => `Go to page ${page}`,
    currentPage: (page: number) => `Page ${page}, current`,
    pageStatus: (page: number) => `Page ${page}`,
    errors: {
      generic: "Try again.",
      forbidden: "This account does not have access to the deck.",
      notFound: "The deck is no longer available.",
      invalid: "The server returned unexpected data.",
      network: "Couldn't reach the server.",
      server: "The server is temporarily unavailable.",
    },
  },
);

function getPreviewErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.generic;
  }
  if (error.status === 403) {
    return messages.errors.forbidden;
  }
  if (error.status === 404) {
    return messages.errors.notFound;
  }
  if (error.code === "INVALID_CATALOG_RESPONSE") {
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

interface CatalogDeckPreviewProps {
  deckUuid: string;
  onClose: () => void;
  onOpenDeck?: () => void;
  returnTarget: DeckDetailsReturnTarget;
  returnUsername?: string;
}

function PreviewChevronIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d={direction === "left" ? "m14.5 6-6 6 6 6" : "m9.5 6 6 6-6 6"} />
    </svg>
  );
}

function usePreviewPaginationWidth(): number {
  const getButtonCount = () => {
    if (typeof window === "undefined") {
      return 7;
    }
    if (window.matchMedia("(max-width: 420px)").matches) {
      return 3;
    }
    return window.matchMedia("(max-width: 760px)").matches ? 5 : 7;
  };
  const [buttonCount, setButtonCount] = useState(getButtonCount);

  useEffect(() => {
    const narrowQuery = window.matchMedia("(max-width: 420px)");
    const compactQuery = window.matchMedia("(max-width: 760px)");
    const updateButtonCount = () => setButtonCount(getButtonCount());
    narrowQuery.addEventListener("change", updateButtonCount);
    compactQuery.addEventListener("change", updateButtonCount);
    return () => {
      narrowQuery.removeEventListener("change", updateButtonCount);
      compactQuery.removeEventListener("change", updateButtonCount);
    };
  }, []);

  return buttonCount;
}

export function CatalogDeckPreview({
  deckUuid,
  onClose,
  onOpenDeck,
  returnTarget,
  returnUsername,
}: CatalogDeckPreviewProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const preview = useCatalogDeckPreview(deckUuid);
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const cardsSectionRef = useRef<HTMLElement | null>(null);
  const dialogLabelId = useId();
  const paginationButtonCount = usePreviewPaginationWidth();

  useEffect(() => {
    const dialog = dialogRef.current;

    if (dialog !== null && !dialog.open) {
      dialog.showModal();
    }
  }, []);

  function closeDialog(): void {
    dialogRef.current?.close();
  }

  function handleCancel(event: SyntheticEvent<HTMLDialogElement>): void {
    event.preventDefault();
    closeDialog();
  }

  function selectPage(page: number): void {
    if (page === preview.currentPage || page < 1 || page > preview.pageCount) {
      return;
    }

    preview.selectPage(page);
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth";
    cardsSectionRef.current?.scrollIntoView({ behavior, block: "start" });
  }

  const deck = preview.deck;
  const updatedAt = deck === null ? null : formatCatalogUpdatedAt(deck.updatedAt, locale);
  const words =
    deck === null ? null : localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale);
  const saves =
    deck === null ? null : localizeCount(deck.savesCount, PREVIEW_SAVE_COUNT_FORMS, locale);

  return (
    <dialog
      aria-labelledby={dialogLabelId}
      aria-modal="true"
      className={styles.previewDialog}
      onCancel={handleCancel}
      onClose={onClose}
      ref={dialogRef}
    >
      <div className={styles.previewShell}>
        <span className={styles.visuallyHidden} id={dialogLabelId}>
          {messages.dialogLabel}
        </span>
        <div className={styles.previewTopbar}>
          <Link
            aria-label={messages.openDeckPage}
            className={styles.previewOpenButton}
            onClick={onOpenDeck}
            state={createDeckDetailsNavigationState(returnTarget, returnUsername)}
            to={getDeckDetailsPath(deckUuid)}
          >
            <span>{messages.openDeck}</span>
            <svg
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.9"
              viewBox="0 0 24 24"
            >
              <path d="M5 12h14m-5-5 5 5-5 5" />
            </svg>
          </Link>
          <button aria-label={messages.close} autoFocus onClick={closeDialog} type="button">
            <svg
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path d="m7 7 10 10M17 7 7 17" />
            </svg>
          </button>
        </div>

        <div
          aria-busy={preview.status === "loading" || preview.isPageLoading}
          className={styles.previewScrollArea}
        >
          {preview.status === "loading" ? (
            <div aria-label={messages.loading} className={styles.previewLoading} role="status">
              <span />
              <span />
              <span />
            </div>
          ) : null}

          {preview.status === "error" ? (
            <div className={styles.previewState} role="alert">
              <h2>{messages.errorTitle}</h2>
              <p>{getPreviewErrorMessage(preview.error, messages)}</p>
              <button onClick={preview.retry} type="button">
                {messages.retry}
              </button>
            </div>
          ) : null}

          {preview.status === "success" && deck !== null && words !== null && saves !== null ? (
            <>
              <header className={styles.previewHero}>
                <div className={styles.previewHeroTopline}>
                  <span
                    aria-label={messages.owner(deck.ownerUsername)}
                    className={styles.previewOwnerBadge}
                    title={`@${deck.ownerUsername}`}
                  >
                    @{deck.ownerUsername}
                  </span>
                </div>

                <h2>{deck.title}</h2>
                <p>{deck.description ?? messages.noDescription}</p>

                <div className={styles.previewFacts}>
                  <dl className={styles.previewKeyStats}>
                    <div>
                      <dt>{words.unit}</dt>
                      <dd>{words.formattedValue}</dd>
                    </div>
                    <div>
                      <dt>{saves.unit}</dt>
                      <dd>{saves.formattedValue}</dd>
                    </div>
                  </dl>
                  {deck.updatedAt !== null && updatedAt !== null ? (
                    <p className={styles.previewUpdatedMeta}>
                      <span>{messages.updated}</span>
                      <time dateTime={deck.updatedAt}>{updatedAt}</time>
                    </p>
                  ) : null}
                </div>
              </header>

              <section
                aria-labelledby={`${dialogLabelId}-cards`}
                className={styles.previewCards}
                ref={cardsSectionRef}
              >
                <div className={styles.previewCardsHeader}>
                  <h3 id={`${dialogLabelId}-cards`}>{messages.cards}</h3>
                </div>

                {deck.totalWordsCount === 0 ? (
                  <p className={styles.previewEmpty}>{messages.noCards}</p>
                ) : preview.isPageLoading ? (
                  <div className={styles.previewPageState} role="status">
                    {messages.loadingPage}
                  </div>
                ) : preview.pageError !== null ? (
                  <div className={styles.previewPageState} role="alert">
                    <p>{messages.pageError}</p>
                    <button onClick={preview.retryPage} type="button">
                      {messages.retry}
                    </button>
                  </div>
                ) : (
                  <ol className={styles.previewCardList}>
                    {preview.cards.map((card, index) => (
                      <li key={card.uuid}>
                        <span className={styles.previewCardNumber}>
                          {(preview.currentPage - 1) * CATALOG_PREVIEW_CARD_PAGE_SIZE + index + 1}
                        </span>
                        <div className={styles.previewCardSide}>
                          <span>{card.frontLang.toLocaleUpperCase(locale)}</span>
                          <p>{card.frontText}</p>
                        </div>
                        <div className={styles.previewCardSide}>
                          <span>{card.backLang.toLocaleUpperCase(locale)}</span>
                          <p>{card.backText}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}

                {preview.pageCount > 1 ? (
                  <nav aria-label={messages.pagination} className={styles.previewPagination}>
                    <span aria-live="polite" className={styles.visuallyHidden} role="status">
                      {messages.pageStatus(preview.currentPage)}
                    </span>
                    <button
                      aria-label={messages.previousPage}
                      className={styles.previewPaginationArrow}
                      disabled={preview.currentPage === 1}
                      onClick={() => selectPage(preview.currentPage - 1)}
                      type="button"
                    >
                      <PreviewChevronIcon direction="left" />
                    </button>
                    <ol className={styles.previewPaginationList}>
                      {getCatalogPaginationTokens(
                        preview.pageCount,
                        preview.currentPage,
                        paginationButtonCount,
                      ).map((token) => (
                        <li key={token.key}>
                          {token.type === "ellipsis" ? (
                            <span aria-hidden="true" className={styles.previewPaginationEllipsis}>
                              …
                            </span>
                          ) : (
                            <button
                              aria-current={
                                token.pageNumber === preview.currentPage ? "page" : undefined
                              }
                              aria-label={
                                token.pageNumber === preview.currentPage
                                  ? messages.currentPage(token.pageNumber)
                                  : messages.goToPage(token.pageNumber)
                              }
                              className={
                                token.pageNumber === preview.currentPage
                                  ? `${styles.previewPaginationButton} ${styles.previewPaginationButtonActive}`
                                  : styles.previewPaginationButton
                              }
                              onClick={() => selectPage(token.pageNumber)}
                              type="button"
                            >
                              {token.pageNumber}
                            </button>
                          )}
                        </li>
                      ))}
                    </ol>
                    <button
                      aria-label={messages.nextPage}
                      className={styles.previewPaginationArrow}
                      disabled={preview.currentPage === preview.pageCount}
                      onClick={() => selectPage(preview.currentPage + 1)}
                      type="button"
                    >
                      <PreviewChevronIcon direction="right" />
                    </button>
                  </nav>
                ) : null}
              </section>
            </>
          ) : null}
        </div>
      </div>
    </dialog>
  );
}
