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
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown | null>(null);
  const [showSavedNotice, setShowSavedNotice] = useState(false);
  const normalizedTitle = title.trim();
  const normalizedDescription = description.trim();
  const descriptionValue = normalizedDescription.length === 0 ? null : normalizedDescription;
  const hasChanges = title !== deck.title || description !== (deck.description ?? "");
  const canSave = normalizedTitle.length > 0 && hasChanges;

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

  return (
    <form
      aria-busy={isSaving}
      className={styles.detailsForm}
      data-deck-details-form={deck.uuid}
      onSubmit={(event) => void handleSubmit(event)}
    >
      <div className={styles.formHeading}>
        <div>
          <span>Основные данные</span>
          <h2>О колоде</h2>
        </div>
        <span className={styles.visibilityBadge}>{deck.isPublic ? "Публичная" : "Приватная"}</span>
      </div>

      <div className={styles.fields}>
        <label className={styles.field}>
          <span>
            <strong>Название</strong>
            <small>{title.length}/150</small>
          </span>
          <input
            autoComplete="off"
            maxLength={150}
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
        <div aria-live="polite" className={styles.cardCount}>
          <DashboardIcon name="book" />
          <span>
            Загружено: <strong>{editor.cards.length}</strong>
          </span>
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
  const editor = useDeckEditor(deckUuid);

  return (
    <main className={styles.page}>
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
                <span className={styles.eyebrow}>Редактор колоды</span>
                <h1 title={editor.deck.title}>{editor.deck.title}</h1>
                <p>Изменяйте данные колоды и управляйте карточками в одном месте.</p>
              </div>
              <div className={styles.headerMetric}>
                <span>{editor.deck.totalWordsCount}</span>
                <small>карточек в колоде</small>
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
