import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { isApiError } from "../../api";
import { DashboardIcon } from "../../components/DashboardVisuals";
import type {
  EditableLibraryDeck,
  UpdateLibraryDeckInput,
} from "../../features/library/model/library-types";
import {
  useDeckEditor,
  type UseDeckEditorResult,
} from "../../features/library/model/useDeckEditor";
import { CARD_COUNT_FORMS, localizeCount, useLocale } from "../../i18n";
import libraryStyles from "../LibraryPage/LibraryPage.module.css";
import styles from "./LibraryDeckEditPage.module.css";
import { LibraryDeckEditCardRow } from "./LibraryDeckEditCardRow";

function getDeckLoadErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось загрузить колоду. Попробуйте ещё раз.";
  }
  if (error.status === 403) {
    return "У вас нет доступа к редактированию этой колоды.";
  }
  if (error.status === 404) {
    return "Колода не найдена или уже удалена.";
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return "Сервер вернул данные колоды в неожиданном формате.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может загрузить колоду.";
  }

  return "Не удалось загрузить колоду. Попробуйте ещё раз.";
}

function getDeckCardsErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось загрузить следующие карточки. Попробуйте ещё раз.";
  }
  if (error.status === 403) {
    return "У вас нет доступа к карточкам этой колоды.";
  }
  if (error.status === 404) {
    return "Колода больше не найдена.";
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return "Сервер вернул карточки в неожиданном формате.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может загрузить карточки.";
  }

  return "Не удалось загрузить следующие карточки. Попробуйте ещё раз.";
}

function getDeckSaveErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось сохранить колоду. Попробуйте ещё раз.";
  }
  if (error.status === 403) {
    return "У вас нет доступа к редактированию этой колоды.";
  }
  if (error.status === 404) {
    return "Колода больше не найдена.";
  }
  if (error.status === 409) {
    return "Сервер отклонил изменения. Попробуйте изменить название.";
  }
  if (error.status === 422) {
    return "Проверьте название и описание колоды.";
  }
  if (error.code === "REQUEST_ABORTED") {
    return "Сохранение было отменено.";
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return "Сервер вернул неожиданный ответ после сохранения.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может сохранить колоду.";
  }

  return "Не удалось сохранить колоду. Попробуйте ещё раз.";
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
  const canSave = normalizedTitle.length >= 3 && normalizedTitle.length <= 50 && hasChanges;

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
          <span>{isPublic ? "Публичная" : "Приватная"}</span>
        </span>
      </div>

      <div className={styles.fields}>
        <label className={styles.field}>
          <span>
            <strong>Название</strong>
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
            <strong>Описание</strong>
            <small>необязательно</small>
          </span>
          <textarea
            maxLength={3000}
            name="description"
            onChange={(event) => {
              setDescription(event.currentTarget.value);
              setShowSavedNotice(false);
            }}
            placeholder="О чём эта колода?"
            rows={4}
            value={description}
          />
        </label>

        <div className={styles.privacyControl}>
          <div className={styles.privacyControlCopy} id="deck-visibility-label">
            <strong>Доступ к колоде</strong>
            <small>
              {isPublic
                ? "Другие пользователи смогут видеть эту колоду."
                : "Колода доступна только вам."}
            </small>
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
                <span>Приватная</span>
              </button>
              <button
                aria-pressed={isPublic}
                className={styles.privacyChoice}
                onClick={() => handlePrivacyChange(true)}
                type="button"
              >
                <VisibilityGlyph isPublic />
                <span>Публичная</span>
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
              {getDeckSaveErrorMessage(saveError)}
            </p>
          )}
          {showSavedNotice && saveError === null ? (
            <p className={styles.savedNotice}>Изменения сохранены</p>
          ) : null}
        </div>
        <button disabled={isSaving || !canSave} type="submit">
          {isSaving ? <span aria-hidden="true" className={styles.spinner} /> : null}
          <span>{isSaving ? "Сохраняем…" : "Сохранить изменения"}</span>
        </button>
      </div>
    </form>
  );
}

function PageLoadingState() {
  return (
    <div aria-label="Загрузка редактора колоды" className={styles.loadingState} role="status">
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
  return (
    <div className={styles.pageState} role="alert">
      <span aria-hidden="true" className={styles.stateMark}>
        Etch
      </span>
      <h1>Колода не загрузилась</h1>
      <p>{getDeckLoadErrorMessage(editor.error)}</p>
      <div>
        <Link to="/library">Вернуться в библиотеку</Link>
        <button onClick={editor.retry} type="button">
          Попробовать снова
        </button>
      </div>
    </div>
  );
}

function CardsSection({ editor }: { editor: UseDeckEditorResult }) {
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
          <span>Состав колоды</span>
          <h2 id="deck-cards-heading" tabIndex={-1}>
            Карточки
          </h2>
        </div>
      </div>

      {editor.cards.length === 0 && !editor.hasMore ? (
        <div className={styles.emptyCards} role="status">
          <span aria-hidden="true">Aa</span>
          <h3>В этой колоде пока нет карточек</h3>
          <p>Добавить карточки можно из вкладки «Карточки» в библиотеке.</p>
          <Link to="/library">Открыть библиотеку</Link>
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
              {getDeckCardsErrorMessage(editor.loadMoreError)}
            </p>
          )}

          {editor.hasMore ? (
            <button
              className={libraryStyles.loadMoreButton}
              disabled={editor.isLoadingMore}
              onClick={editor.loadMore}
              type="button"
            >
              <span>{editor.isLoadingMore ? "Загружаем…" : "Загрузить больше"}</span>
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
  const editor = useDeckEditor(deckUuid);
  const deckCardCount = localizeCount(editor.deck?.totalWordsCount ?? 0, CARD_COUNT_FORMS, locale);

  return (
    <main className={`${libraryStyles.page} ${styles.page}`}>
      <div className={styles.editor}>
        {editor.status === "loading" ? <PageLoadingState /> : null}
        {editor.status === "error" ? <PageErrorState editor={editor} /> : null}
        {editor.status === "success" && editor.deck !== null ? (
          <>
            <header className={styles.header}>
              <Link aria-label="Вернуться в библиотеку" className={styles.backLink} to="/library">
                <BackGlyph />
              </Link>
              <div className={styles.headerCopy}>
                <div className={styles.headerTopline}>
                  <span className={styles.eyebrow}>Редактор колоды</span>
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
                <h1 title={editor.deck.title}>{editor.deck.title}</h1>
                <p>Изменяйте данные колоды и управляйте карточками в одном месте.</p>
              </div>
            </header>

            <DeckDetailsForm deck={editor.deck} onSave={editor.saveDeck} />
            <CardsSection editor={editor} />
          </>
        ) : null}
      </div>
    </main>
  );
}

export default LibraryDeckEditPage;
