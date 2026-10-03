import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { API_ERROR_CODES, hasApiErrorCode, isApiError } from "../../api";
import { isValidDeckTitle } from "../../features/library/model/input-validation";
import { DashboardIcon } from "../../components/DashboardVisuals";
import type {
  EditableLibraryDeck,
  UpdateLibraryDeckInput,
} from "../../features/library/model/library-types";
import {
  useDeckEditor,
  type UseDeckEditorResult,
} from "../../features/library/model/useDeckEditor";
import { useLongTextPreviewsEnabled } from "../../features/settings/model/useLongTextPreviewsEnabled";
import {
  CARD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
} from "../../i18n";
import libraryStyles from "../LibraryPage/LibraryPage.module.css";
import styles from "./LibraryDeckEditPage.module.css";
import { LibraryDeckEditCardRow } from "./LibraryDeckEditCardRow";

const MESSAGES = defineMessages(
  {
    loadErrors: {
      default: "Не удалось загрузить колоду. Попробуйте ещё раз.",
      notFound: "Колода не найдена или уже удалена.",
      invalid: "Сервер вернул данные колоды в неожиданном формате.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      server: "Сервер временно не может загрузить колоду.",
    },
    cardsErrors: {
      default: "Не удалось загрузить следующие карточки. Попробуйте ещё раз.",
      notFound: "Колода больше не найдена.",
      invalid: "Сервер вернул карточки в неожиданном формате.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      server: "Сервер временно не может загрузить карточки.",
    },
    saveErrors: {
      default: "Не удалось сохранить колоду. Попробуйте ещё раз.",
      notFound: "Колода больше не найдена.",
      conflict: "Сервер отклонил изменения. Попробуйте изменить название.",
      validation: "Проверьте название и описание колоды.",
      aborted: "Сохранение было отменено.",
      invalid: "Сервер вернул неожиданный ответ после сохранения.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      server: "Сервер временно не может сохранить колоду.",
    },
    public: "Публичная",
    private: "Приватная",
    title: "Название",
    description: "Описание",
    optional: "необязательно",
    descriptionPlaceholder: "О чём эта колода?",
    access: "Доступ к колоде",
    publicDescription: "Другие пользователи смогут видеть эту колоду.",
    privateDescription: "Колода доступна только вам.",
    saved: "Изменения сохранены",
    saving: "Сохраняем…",
    save: "Сохранить изменения",
    loading: "Загрузка редактора колоды",
    pageErrorTitle: "Колода не загрузилась",
    backToLibrary: "Вернуться в библиотеку",
    retry: "Попробовать снова",
    deckContents: "Состав колоды",
    cards: "Карточки",
    emptyTitle: "В этой колоде пока нет карточек",
    emptyDescription: "Добавить карточки можно из вкладки «Карточки» в библиотеке.",
    openLibrary: "Открыть библиотеку",
    loadingMore: "Загружаем…",
    loadMore: "Загрузить больше",
    editor: "Редактор колоды",
    lead: "Изменяйте данные колоды и управляйте карточками в одном месте.",
  },
  {
    loadErrors: {
      default: "Couldn't load the deck. Please try again.",
      notFound: "The deck was not found or has already been deleted.",
      invalid: "The server returned the deck in an unexpected format.",
      network: "Couldn't reach the server. Check your connection.",
      server: "The server can't load the deck right now.",
    },
    cardsErrors: {
      default: "Couldn't load more cards. Please try again.",
      notFound: "The deck is no longer available.",
      invalid: "The server returned the cards in an unexpected format.",
      network: "Couldn't reach the server. Check your connection.",
      server: "The server can't load the cards right now.",
    },
    saveErrors: {
      default: "Couldn't save the deck. Please try again.",
      notFound: "The deck is no longer available.",
      conflict: "The server rejected the changes. Try a different title.",
      validation: "Check the deck title and description.",
      aborted: "Saving was canceled.",
      invalid: "The server returned an unexpected response after saving.",
      network: "Couldn't reach the server. Check your connection.",
      server: "The server can't save the deck right now.",
    },
    public: "Public",
    private: "Private",
    title: "Title",
    description: "Description",
    optional: "optional",
    descriptionPlaceholder: "What is this deck about?",
    access: "Deck access",
    publicDescription: "Other users will be able to see this deck.",
    privateDescription: "Only you can access this deck.",
    saved: "Changes saved",
    saving: "Saving…",
    save: "Save changes",
    loading: "Loading deck editor",
    pageErrorTitle: "The deck couldn't be loaded",
    backToLibrary: "Back to library",
    retry: "Try again",
    deckContents: "Deck contents",
    cards: "Cards",
    emptyTitle: "This deck has no cards yet",
    emptyDescription: "You can add cards from the Cards tab in your library.",
    openLibrary: "Open library",
    loadingMore: "Loading…",
    loadMore: "Load more",
    editor: "Deck editor",
    lead: "Edit deck details and manage its cards in one place.",
  },
);

type DeckLoadErrorMessages = (typeof MESSAGES)["ru-RU"]["loadErrors"];
type DeckCardsErrorMessages = (typeof MESSAGES)["ru-RU"]["cardsErrors"];
type DeckSaveErrorMessages = (typeof MESSAGES)["ru-RU"]["saveErrors"];

function getDeckLoadErrorMessage(error: unknown, messages: DeckLoadErrorMessages): string {
  if (!isApiError(error)) {
    return messages.default;
  }
  if (error.status === 403 || error.status === 404) {
    return messages.notFound;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.invalid;
  }
  if (error.status === 0) {
    return messages.network;
  }
  if (error.status >= 500) {
    return messages.server;
  }

  return messages.default;
}

function getDeckCardsErrorMessage(error: unknown, messages: DeckCardsErrorMessages): string {
  if (!isApiError(error)) {
    return messages.default;
  }
  if (error.status === 403 || error.status === 404) {
    return messages.notFound;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.invalid;
  }
  if (error.status === 0) {
    return messages.network;
  }
  if (error.status >= 500) {
    return messages.server;
  }

  return messages.default;
}

function getDeckSaveErrorMessage(error: unknown, messages: DeckSaveErrorMessages): string {
  if (!isApiError(error)) {
    return messages.default;
  }
  if (error.status === 403 || error.status === 404) {
    return messages.notFound;
  }
  if (hasApiErrorCode(error, API_ERROR_CODES.deckAlreadyExists) || error.status === 409) {
    return messages.conflict;
  }
  if (error.status === 422) {
    return messages.validation;
  }
  if (error.code === "REQUEST_ABORTED") {
    return messages.aborted;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.invalid;
  }
  if (error.status === 0) {
    return messages.network;
  }
  if (error.status >= 500) {
    return messages.server;
  }

  return messages.default;
}

function BackGlyph() {
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
      <path d="m14.5 5-7 7 7 7M8 12h10" />
    </svg>
  );
}

function VisibilityGlyph({ isPublic }: { isPublic: boolean }) {
  if (isPublic) {
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
        <circle cx="12" cy="12" r="8.5" />
        <path d="M3.8 12h16.4M12 3.5c2.2 2.3 3.3 5.1 3.3 8.5S14.2 18.2 12 20.5C9.8 18.2 8.7 15.4 8.7 12S9.8 5.8 12 3.5Z" />
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
      <rect height="9" rx="2.4" width="14" x="5" y="10.5" />
      <path d="M8.2 10.5V8a3.8 3.8 0 0 1 7.6 0v2.5M12 14.2v2.2" />
    </svg>
  );
}

function DeckDetailsForm({
  deck,
  onSave,
}: {
  deck: EditableLibraryDeck;
  onSave: (input: UpdateLibraryDeckInput) => Promise<void>;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const isMountedRef = useRef(true);
  const isSavingRef = useRef(false);
  const [title, setTitle] = useState(deck.title);
  const [description, setDescription] = useState(deck.description ?? "");
  const [isPublic, setIsPublic] = useState(deck.isPublic);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown | null>(null);
  const [showSavedNotice, setShowSavedNotice] = useState(false);
  const normalizedTitle = title.trim();
  const normalizedDescription = description.trim();
  const descriptionValue = normalizedDescription.length === 0 ? null : normalizedDescription;
  const hasChanges =
    title !== deck.title || description !== (deck.description ?? "") || isPublic !== deck.isPublic;
  const canSave = isValidDeckTitle(normalizedTitle) && hasChanges;

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isSavingRef.current || !canSave) {
      return;
    }

    isSavingRef.current = true;
    setIsSaving(true);
    setSaveError(null);
    setShowSavedNotice(false);

    try {
      await onSave({
        title: normalizedTitle,
        description: descriptionValue,
        isPublic,
      });
      if (isMountedRef.current) {
        setTitle(normalizedTitle);
        setDescription(descriptionValue ?? "");
        setShowSavedNotice(true);
      }
    } catch (error: unknown) {
      if (isMountedRef.current) {
        setSaveError(error);
      }
    } finally {
      isSavingRef.current = false;
      if (isMountedRef.current) {
        setIsSaving(false);
      }
    }
  }

  function handlePrivacyChange(nextIsPublic: boolean): void {
    if (nextIsPublic === isPublic) {
      return;
    }

    setIsPublic(nextIsPublic);
    setShowSavedNotice(false);
  }

  return (
    <form
      aria-busy={isSaving}
      className={styles.detailsForm}
      data-deck-details-form={deck.uuid}
      onSubmit={(event) => void handleSubmit(event)}
    >
      <div className={styles.formHeading}>
        <div aria-hidden="true" className={styles.abstractVisual} data-deck-abstract-visual>
          <span className={styles.abstractGlow} />
          <span className={styles.abstractOrbit}>
            <i />
          </span>
          <span className={`${styles.abstractCard} ${styles.abstractCardBack}`}>
            <i />
            <i />
            <i />
          </span>
          <span className={`${styles.abstractCard} ${styles.abstractCardFront}`}>
            <i />
            <i />
            <i />
          </span>
          <span className={styles.abstractSpark} />
        </div>
        <span className={styles.visibilityBadge} data-public={isPublic}>
          <VisibilityGlyph isPublic={isPublic} />
          <span>{isPublic ? messages.public : messages.private}</span>
        </span>
      </div>

      <div className={styles.fields}>
        <label className={styles.field}>
          <span>
            <strong>
              {messages.title} <span aria-hidden="true">*</span>
            </strong>
            <small>{title.length}/50</small>
          </span>
          <input
            autoComplete="off"
            maxLength={50}
            minLength={3}
            name="title"
            onChange={(event) => {
              setTitle(event.currentTarget.value);
              setShowSavedNotice(false);
            }}
            required
            value={title}
          />
        </label>

        <label className={styles.field}>
          <span>
            <strong>{messages.description}</strong>
            <small>{messages.optional}</small>
          </span>
          <textarea
            maxLength={3000}
            name="description"
            onChange={(event) => {
              setDescription(event.currentTarget.value);
              setShowSavedNotice(false);
            }}
            placeholder={messages.descriptionPlaceholder}
            rows={4}
            value={description}
          />
        </label>

        <div className={styles.privacyControl}>
          <div className={styles.privacyControlCopy} id="deck-visibility-label">
            <strong>{messages.access}</strong>
            <small>{isPublic ? messages.publicDescription : messages.privateDescription}</small>
          </div>
          <div
            aria-labelledby="deck-visibility-label"
            className={styles.privacyToggle}
            data-public={isPublic}
            role="group"
          >
            <div className={styles.privacyTrack}>
              <button
                aria-pressed={!isPublic}
                className={styles.privacyChoice}
                onClick={() => handlePrivacyChange(false)}
                type="button"
              >
                <VisibilityGlyph isPublic={false} />
                <span>{messages.private}</span>
              </button>
              <button
                aria-pressed={isPublic}
                className={styles.privacyChoice}
                onClick={() => handlePrivacyChange(true)}
                type="button"
              >
                <VisibilityGlyph isPublic />
                <span>{messages.public}</span>
              </button>
              <span aria-hidden="true" className={styles.privacyThumb} />
            </div>
          </div>
        </div>
      </div>

      <div className={styles.formFooter}>
        <div aria-live="polite" className={styles.saveStatus}>
          {saveError === null ? null : (
            <p className={styles.formError} role="alert">
              {getDeckSaveErrorMessage(saveError, messages.saveErrors)}
            </p>
          )}
          {showSavedNotice && saveError === null ? (
            <p className={styles.savedNotice}>{messages.saved}</p>
          ) : null}
        </div>
        <button disabled={isSaving || !canSave} type="submit">
          {isSaving ? <span aria-hidden="true" className={styles.spinner} /> : null}
          <span>{isSaving ? messages.saving : messages.save}</span>
        </button>
      </div>
    </form>
  );
}

function PageLoadingState() {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div aria-label={messages.loading} className={styles.loadingState} role="status">
      <span className={styles.loadingHeading} />
      <span className={styles.loadingForm} />
      <div className={styles.loadingCards}>
        {Array.from({ length: 4 }, (_, index) => (
          <span key={index} />
        ))}
      </div>
    </div>
  );
}

function PageErrorState({ editor }: { editor: UseDeckEditorResult }) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div className={styles.pageState} role="alert">
      <span aria-hidden="true" className={styles.stateMark}>
        Etch
      </span>
      <h1>{messages.pageErrorTitle}</h1>
      <p>{getDeckLoadErrorMessage(editor.error, messages.loadErrors)}</p>
      <div>
        <Link to="/library">{messages.backToLibrary}</Link>
        <button onClick={editor.retry} type="button">
          {messages.retry}
        </button>
      </div>
    </div>
  );
}

function CardsSection({ editor }: { editor: UseDeckEditorResult }) {
  const messages = useLocalizedMessages(MESSAGES);
  const deck = editor.deck;

  if (deck === null) {
    return null;
  }

  return (
    <section
      aria-busy={editor.isLoadingMore}
      aria-labelledby="deck-cards-heading"
      className={styles.cardsSection}
    >
      <div className={styles.sectionHeading}>
        <div>
          <span>{messages.deckContents}</span>
          <h2 id="deck-cards-heading" tabIndex={-1}>
            {messages.cards}
          </h2>
        </div>
      </div>

      {editor.cards.length === 0 && !editor.hasMore ? (
        <div className={styles.emptyCards} role="status">
          <span aria-hidden="true">Aa</span>
          <h3>{messages.emptyTitle}</h3>
          <p>{messages.emptyDescription}</p>
          <Link to="/library">{messages.openLibrary}</Link>
        </div>
      ) : (
        <>
          <ul className={libraryStyles.cardsList}>
            {editor.cards.map((card) => (
              <LibraryDeckEditCardRow
                card={card}
                key={card.uuid}
                onRemove={editor.removeCard}
                onUpdate={editor.updateCard}
              />
            ))}
          </ul>

          {editor.loadMoreError === null ? null : (
            <p className={styles.loadMoreError} role="alert">
              {getDeckCardsErrorMessage(editor.loadMoreError, messages.cardsErrors)}
            </p>
          )}

          {editor.hasMore ? (
            <button
              className={libraryStyles.loadMoreButton}
              disabled={editor.isLoadingMore}
              onClick={editor.loadMore}
              type="button"
            >
              <span>{editor.isLoadingMore ? messages.loadingMore : messages.loadMore}</span>
              <DashboardIcon name="chevron" />
            </button>
          ) : null}
        </>
      )}
    </section>
  );
}

export function LibraryDeckEditPage() {
  const { deck_uuid: deckUuid = "" } = useParams<{ deck_uuid: string }>();
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const longTextPreviewsEnabled = useLongTextPreviewsEnabled();
  const editor = useDeckEditor(deckUuid);
  const deckCardCount = localizeCount(editor.deck?.totalWordsCount ?? 0, CARD_COUNT_FORMS, locale);

  return (
    <main className={`${libraryStyles.page} ${styles.page}`}>
      <div className={styles.editor}>
        {editor.status === "loading" ? <PageLoadingState /> : null}
        {editor.status === "error" ? <PageErrorState editor={editor} /> : null}
        {editor.status === "success" && editor.deck !== null ? (
          <div className={styles.loadedContent}>
            <header className={styles.header}>
              <Link aria-label={messages.backToLibrary} className={styles.backLink} to="/library">
                <BackGlyph />
              </Link>
              <div className={styles.headerCopy}>
                <div className={styles.headerTopline}>
                  <span className={styles.eyebrow}>{messages.editor}</span>
                  <div
                    aria-live="polite"
                    aria-label={deckCardCount.text}
                    className={styles.headerMetric}
                  >
                    <DashboardIcon name="book" />
                    <span>
                      <strong>{deckCardCount.formattedValue}</strong> {deckCardCount.unit}
                    </span>
                  </div>
                </div>
                <h1 title={longTextPreviewsEnabled ? editor.deck.title : undefined}>
                  {editor.deck.title}
                </h1>
                <p>{messages.lead}</p>
              </div>
            </header>

            <DeckDetailsForm deck={editor.deck} onSave={editor.saveDeck} />
            <CardsSection editor={editor} />
          </div>
        ) : null}
      </div>
    </main>
  );
}

export default LibraryDeckEditPage;
