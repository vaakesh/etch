import { useEffect, useId, useRef, type SyntheticEvent } from "react";
import { isApiError } from "../../api";
import { formatCatalogUpdatedAt } from "../../features/catalog/model/catalog-formatters";
import { useCatalogDeckPreview } from "../../features/catalog/model/useCatalogDeckPreview";
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
    yourDeck: "Ваша колода",
    otherOwner: "Другой пользователь",
    owner: "Владелец",
    words: "Слов",
    saves: "Сохранений",
    edited: "Изменено",
    noDescription: "Без описания",
    cards: "Карточки",
    cardsLoaded: (loaded: number, total: number) => `${loaded} из ${total}`,
    noCards: "В этой колоде пока нет карточек",
    loading: "Загружаем предпросмотр…",
    errorTitle: "Предпросмотр не загрузился",
    retry: "Попробовать снова",
    loadMore: "Показать ещё",
    loadingMore: "Загружаем…",
    loadMoreError: "Не удалось загрузить следующие карточки.",
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
    yourDeck: "Your deck",
    otherOwner: "Another user",
    owner: "Owner",
    words: "Words",
    saves: "Saves",
    edited: "Edited",
    noDescription: "No description",
    cards: "Cards",
    cardsLoaded: (loaded: number, total: number) => `${loaded} of ${total}`,
    noCards: "This deck has no cards yet",
    loading: "Loading preview…",
    errorTitle: "Preview didn't load",
    retry: "Try again",
    loadMore: "Show more",
    loadingMore: "Loading…",
    loadMoreError: "Couldn't load the next cards.",
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
  currentUserUuid: string;
  deckUuid: string;
  onClose: () => void;
}

export function CatalogDeckPreview({
  currentUserUuid,
  deckUuid,
  onClose,
}: CatalogDeckPreviewProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const preview = useCatalogDeckPreview(deckUuid);
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const dialogLabelId = useId();

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
  }

  const deck = preview.deck;
  const ownerUsername =
    deck?.ownerUuid === currentUserUuid ? messages.yourDeck : messages.otherOwner;
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
          aria-busy={preview.status === "loading" || preview.isLoadingMore}
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
                <h2>{deck.title}</h2>
                <p>{deck.description ?? messages.noDescription}</p>

                <dl className={styles.previewMeta}>
                  <div>
                    <dt>{messages.owner}</dt>
                    <dd>{ownerUsername}</dd>
                  </div>
                  <div>
                    <dt>{messages.words}</dt>
                    <dd>{words.formattedValue}</dd>
                  </div>
                  <div>
                    <dt>{messages.saves}</dt>
                    <dd>{saves.formattedValue}</dd>
                  </div>
                  {deck.updatedAt !== null && updatedAt !== null ? (
                    <div>
                      <dt>{messages.edited}</dt>
                      <dd>
                        <time dateTime={deck.updatedAt}>{updatedAt}</time>
                      </dd>
                    </div>
                  ) : null}
                </dl>
              </header>

              <section aria-labelledby={`${dialogLabelId}-cards`} className={styles.previewCards}>
                <div className={styles.previewCardsHeader}>
                  <h3 id={`${dialogLabelId}-cards`}>{messages.cards}</h3>
                  <span aria-live="polite">
                    {messages.cardsLoaded(preview.cards.length, deck.totalWordsCount)}
                  </span>
                </div>

                {preview.cards.length === 0 ? (
                  <p className={styles.previewEmpty}>{messages.noCards}</p>
                ) : (
                  <ol className={styles.previewCardList}>
                    {preview.cards.map((card, index) => (
                      <li key={card.uuid}>
                        <span className={styles.previewCardNumber}>{index + 1}</span>
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

                {preview.hasMore ? (
                  <div className={styles.previewLoadMore}>
                    <button
                      disabled={preview.isLoadingMore}
                      onClick={preview.loadMore}
                      type="button"
                    >
                      {preview.isLoadingMore ? messages.loadingMore : messages.loadMore}
                    </button>
                    {preview.loadMoreError === null ? null : (
                      <p role="alert">{messages.loadMoreError}</p>
                    )}
                  </div>
                ) : null}
              </section>
            </>
          ) : null}
        </div>
      </div>
    </dialog>
  );
}
