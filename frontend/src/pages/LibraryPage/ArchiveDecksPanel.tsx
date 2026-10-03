import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { isApiError } from "../../api";
import {
  createDeckDetailsNavigationState,
  getDeckDetailsPath,
} from "../../features/decks/model/deck-details-navigation";
import { setCachedLibraryDecks } from "../../features/library/model/library-decks-cache";
import {
  useArchiveOffers,
  useArchivePreview,
  usePreserveArchivedDeck,
} from "../../features/library/model/useArchivedDecks";
import {
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
} from "../../i18n";
import styles from "./LibraryPage.module.css";
import { ArchiveIcon } from "./ArchiveIcon";

const MESSAGES = defineMessages(
  {
    title: "Архивные колоды",
    description: "Колоды, к которым изменился доступ. Их карточки доступны до указанной даты.",
    emptyTitle: "Архив пуст",
    emptyDescription: "Когда доступная вам колода попадёт в архив, она появится здесь.",
    loadError: "Не удалось загрузить архивные колоды.",
    previewError: "Не удалось открыть архивную колоду.",
    cardsError: "Не удалось загрузить следующие карточки.",
    forbidden: "Доступ к этой архивной колоде больше недоступен.",
    expired: "Срок хранения этой архивной колоды истёк.",
    invalid: "Сервер вернул данные архива в неожиданном формате.",
    network: "Не удалось связаться с сервером. Проверьте подключение.",
    retry: "Попробовать снова",
    loading: "Загружаем архив…",
    loadingDeck: "Загружаем карточки…",
    loadingMore: "Загружаем…",
    showMore: "Показать ещё",
    open: "Посмотреть карточки",
    close: "Свернуть карточки",
    restore: "Восстановить",
    restoring: "Восстанавливаем…",
    openCopy: "Открыть копию",
    restoreError: "Не удалось восстановить колоду. Попробуйте ещё раз.",
    copyDeleted: "Сохранённая копия уже удалена. Повторное восстановление недоступно.",
    restoreConflict: "Не удалось перенести прогресс в восстановленную колоду.",
    expires: (date: string) => `Доступна до ${date}`,
    preserved: "Сохранена в библиотеку",
    noCards: "В этой колоде нет карточек.",
    front: "Слово",
    back: "Перевод",
    reasons: {
      deleted: "Колода удалена",
      owner_deleted: "Автор удалил аккаунт",
      made_private: "Колода стала приватной",
    },
  },
  {
    title: "Archived decks",
    description: "Decks whose access has changed. Their cards are available until the date shown.",
    emptyTitle: "No archived decks",
    emptyDescription: "Any archived decks available to you will appear here.",
    loadError: "We couldn't load archived decks.",
    previewError: "We couldn't open this archived deck.",
    cardsError: "We couldn't load the next cards.",
    forbidden: "This archived deck is no longer available to you.",
    expired: "This archived deck has expired.",
    invalid: "The server returned unexpected archive data.",
    network: "We couldn't reach the server. Check your connection.",
    retry: "Try again",
    loading: "Loading archive…",
    loadingDeck: "Loading cards…",
    loadingMore: "Loading…",
    showMore: "Show more",
    open: "View cards",
    close: "Hide cards",
    restore: "Restore",
    restoring: "Restoring…",
    openCopy: "Open copy",
    restoreError: "We couldn't restore this deck. Try again.",
    copyDeleted: "The saved copy was deleted. This deck cannot be restored again.",
    restoreConflict: "We couldn't transfer your progress to the restored deck.",
    expires: (date: string) => `Available until ${date}`,
    preserved: "Saved to library",
    noCards: "This deck has no cards.",
    front: "Word",
    back: "Translation",
    reasons: {
      deleted: "Deck deleted",
      owner_deleted: "Author deleted their account",
      made_private: "Deck made private",
    },
  },
);

function errorText(error: unknown, fallback: string, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) return fallback;
  if (error.status === 403 || error.status === 404) return messages.forbidden;
  if (error.status === 410) return messages.expired;
  if (error.code === "INVALID_ARCHIVE_RESPONSE") return messages.invalid;
  if (error.status === 0) return messages.network;
  return fallback;
}

function ArchivePreview({ deckUuid }: { deckUuid: string }) {
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const preview = useArchivePreview(deckUuid);

  if (preview.status === "loading") {
    return (
      <p className={styles.archiveFeedback} role="status">
        {messages.loadingDeck}
      </p>
    );
  }
  if (preview.status === "error" || preview.deck === null) {
    return (
      <div className={styles.archiveFeedback} role="alert">
        <p>{errorText(preview.error, messages.previewError, messages)}</p>
        <button onClick={preview.retry} type="button">
          {messages.retry}
        </button>
      </div>
    );
  }

  const count = localizeCount(preview.deck.wordsCount, WORD_COUNT_FORMS, locale);
  return (
    <div className={styles.archivePreview}>
      <div className={styles.archivePreviewHeader}>
        <span>{messages.reasons[preview.deck.archiveReason]}</span>
        <span>
          <strong>{count.formattedValue}</strong> {count.unit}
        </span>
      </div>
      {preview.deck.description ? (
        <p className={styles.archiveDescription}>{preview.deck.description}</p>
      ) : null}
      {preview.cards.length === 0 ? (
        <p className={styles.archiveFeedback}>{messages.noCards}</p>
      ) : (
        <ol className={styles.archiveCards}>
          {preview.cards.map((card) => (
            <li className={styles.archiveCard} key={card.uuid}>
              <div>
                <small>
                  {messages.front} · {card.frontLang.toUpperCase()}
                </small>
                <span>{card.frontText}</span>
              </div>
              <div>
                <small>
                  {messages.back} · {card.backLang.toUpperCase()}
                </small>
                <span>{card.backText}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
      {preview.loadMoreError ? (
        <p className={styles.archiveError} role="alert">
          {errorText(preview.loadMoreError, messages.cardsError, messages)}
        </p>
      ) : null}
      {preview.hasMore ? (
        <button
          className={styles.archiveMore}
          disabled={preview.isLoadingMore}
          onClick={preview.loadMore}
          type="button"
        >
          {preview.isLoadingMore ? messages.loadingMore : messages.showMore}
        </button>
      ) : null}
    </div>
  );
}

export function ArchiveDecksPanel() {
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const navigate = useNavigate();
  const archive = useArchiveOffers();
  const restoration = usePreserveArchivedDeck();
  const [openUuid, setOpenUuid] = useState<string | null>(null);
  const dateFormatter = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  async function handleRestore(deckUuid: string): Promise<void> {
    const result = await restoration.preserve(deckUuid);
    if (result === null || result.copyDeleted) return;
    setCachedLibraryDecks(null);
    void navigate(getDeckDetailsPath(result.uuid), {
      state: createDeckDetailsNavigationState("library"),
    });
  }

  return (
    <div aria-busy={archive.status === "loading"} className={styles.archivePanel}>
      <header className={styles.archiveHeading}>
        <h2 className={styles.visuallyHidden}>{messages.title}</h2>
        <p>{messages.description}</p>
        {archive.status === "success" ? (
          <span
            aria-label={`${messages.title}: ${archive.offers.length}`}
            className={styles.archiveCount}
          >
            {archive.offers.length}
          </span>
        ) : null}
      </header>
      {archive.status === "loading" ? (
        <p className={styles.archiveFeedback} role="status">
          {messages.loading}
        </p>
      ) : null}
      {archive.status === "error" ? (
        <div className={styles.archiveFeedback} role="alert">
          <p>{errorText(archive.error, messages.loadError, messages)}</p>
          <button onClick={archive.retry} type="button">
            {messages.retry}
          </button>
        </div>
      ) : null}
      {archive.status === "success" && archive.offers.length === 0 ? (
        <div className={styles.archiveFeedback} role="status">
          <span className={styles.archiveEmptyIcon}>
            <ArchiveIcon />
          </span>
          <h3>{messages.emptyTitle}</h3>
          <p>{messages.emptyDescription}</p>
        </div>
      ) : null}
      {archive.status === "success" && archive.offers.length > 0 ? (
        <ul className={styles.archiveList}>
          {archive.offers.map((offer) => {
            const isOpen = offer.uuid === openUuid;
            const previewId = `archive-preview-${offer.uuid}`;
            return (
              <li className={styles.archiveItem} data-open={isOpen} key={offer.uuid}>
                <div className={styles.archiveItemSummary}>
                  <span className={styles.archiveItemIcon}>
                    <ArchiveIcon />
                  </span>
                  <div className={styles.archiveItemText}>
                    <h3>{offer.title}</h3>
                    <p>{messages.expires(dateFormatter.format(new Date(offer.expiresAt)))}</p>
                    {offer.preservedDeckUuid ? (
                      <span className={styles.archiveBadge}>{messages.preserved}</span>
                    ) : null}
                  </div>
                  <div className={styles.archiveActions}>
                    <button
                      aria-controls={previewId}
                      aria-expanded={isOpen}
                      className={styles.archiveOpen}
                      onClick={() => setOpenUuid(isOpen ? null : offer.uuid)}
                      type="button"
                    >
                      <span>{isOpen ? messages.close : messages.open}</span>
                      <svg
                        aria-hidden="true"
                        fill="none"
                        stroke="currentColor"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="1.8"
                        viewBox="0 0 24 24"
                      >
                        <path d="m8 10 4 4 4-4" />
                      </svg>
                    </button>
                    <button
                      className={styles.archiveRestore}
                      disabled={
                        restoration.pendingUuid !== null ||
                        restoration.deletedCopyUuid === offer.uuid
                      }
                      onClick={() => void handleRestore(offer.uuid)}
                      type="button"
                    >
                      <svg
                        aria-hidden="true"
                        fill="none"
                        stroke="currentColor"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="1.8"
                        viewBox="0 0 24 24"
                      >
                        <path d="M4 12a8 8 0 1 1 2.3 5.7M4 17v-5h5M12 8v5l3 2" />
                      </svg>
                      <span>
                        {restoration.pendingUuid === offer.uuid
                          ? messages.restoring
                          : offer.preservedDeckUuid
                            ? messages.openCopy
                            : messages.restore}
                      </span>
                    </button>
                  </div>
                </div>
                {restoration.deletedCopyUuid === offer.uuid ? (
                  <p className={styles.archiveError} role="status">
                    {messages.copyDeleted}
                  </p>
                ) : null}
                {restoration.failedUuid === offer.uuid ? (
                  <p className={styles.archiveError} role="alert">
                    {isApiError(restoration.error) &&
                    restoration.error.code === "DECK_PROGRESS_CONFLICT"
                      ? messages.restoreConflict
                      : errorText(restoration.error, messages.restoreError, messages)}
                  </p>
                ) : null}
                <div hidden={!isOpen} id={previewId}>
                  {isOpen ? <ArchivePreview deckUuid={offer.uuid} /> : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
