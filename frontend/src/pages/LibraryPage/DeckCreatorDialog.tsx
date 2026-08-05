import { useEffect, useId, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { isApiError } from "../../api";
import type { CreateLibraryDeckInput } from "../../features/library/model/library-types";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import styles from "./LibraryPage.module.css";

const MESSAGES = defineMessages(
  {
    errors: {
      generic: "Не удалось создать колоду. Попробуйте ещё раз.",
      forbidden: "У вас нет доступа к созданию колод.",
      conflict: "Сервер отклонил новую колоду. Попробуйте изменить название.",
      validation: "Проверьте название и остальные поля колоды.",
      invalid: "Сервер вернул неожиданный ответ после создания колоды.",
      aborted: "Создание колоды было отменено.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      server: "Сервер временно не может создать колоду.",
    },
    eyebrow: "Новая коллекция",
    title: "Новая колода",
    description: "Задайте название, описание и уровень приватности.",
    close: "Закрыть окно создания колоды",
    deckTitle: "Название",
    deckDescription: "Описание",
    optional: "необязательно",
    descriptionPlaceholder: "О чём эта колода?",
    privacy: "Приватность",
    private: "Приватная",
    privateDescription: "Не публикуется в общем доступе",
    public: "Публичная",
    publicDescription: "Появляется в публичной библиотеке",
    footer: "Новая колода появится первой в вашей библиотеке.",
    cancel: "Отмена",
    creating: "Создаём…",
    create: "Создать",
  },
  {
    errors: {
      generic: "We couldn't create the deck. Try again.",
      forbidden: "You do not have permission to create decks.",
      conflict: "The server rejected this deck. Try a different title.",
      validation: "Check the title and the other deck fields.",
      invalid: "The server returned an unexpected response after creating the deck.",
      aborted: "Deck creation was canceled.",
      network: "We couldn't reach the server. Check your connection.",
      server: "The server cannot create a deck right now.",
    },
    eyebrow: "New collection",
    title: "New deck",
    description: "Add a title, description, and privacy level.",
    close: "Close new deck dialog",
    deckTitle: "Title",
    deckDescription: "Description",
    optional: "optional",
    descriptionPlaceholder: "What is this deck about?",
    privacy: "Privacy",
    private: "Private",
    privateDescription: "Only visible to you",
    public: "Public",
    publicDescription: "Appears in the public library",
    footer: "Your new deck will appear first in your library.",
    cancel: "Cancel",
    creating: "Creating…",
    create: "Create",
  },
);

interface DeckCreatorDialogProps {
  onClose: () => void;
  onSave: (input: CreateLibraryDeckInput) => Promise<void>;
}

function getDeckCreateErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.generic;
  }
  if (error.status === 403) {
    return messages.errors.forbidden;
  }
  if (error.status === 409) {
    return messages.errors.conflict;
  }
  if (error.status === 422) {
    return messages.errors.validation;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.errors.invalid;
  }
  if (error.code === "REQUEST_ABORTED") {
    return messages.errors.aborted;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.server;
  }

  return messages.errors.generic;
}

function DeckCreatorGlyph({ name }: { name: "close" | "deck" | "save" }) {
  if (name === "close") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="m7 7 10 10M17 7 7 17" />
      </svg>
    );
  }

  if (name === "deck") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="M5 6.5h10.5A3.5 3.5 0 0 1 19 10v9H8.5A3.5 3.5 0 0 1 5 15.5v-9Z" />
        <path d="M8 3.5h8.5A2.5 2.5 0 0 1 19 6v8M9 11h6M12 8v6" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path d="M5 4h11l3 3v13H5V4Z" />
      <path d="M8 4v6h8V4M8 20v-6h8v6" />
    </svg>
  );
}

export function DeckCreatorDialog({ onClose, onSave }: DeckCreatorDialogProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const isMountedRef = useRef(true);
  const isSavingRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();
  const deckTitleId = useId();
  const deckDescriptionId = useId();
  const privacyLegendId = useId();
  const privateId = useId();
  const publicId = useId();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown | null>(null);
  const normalizedTitleLength = title.trim().length;
  const canSave = normalizedTitleLength >= 3 && normalizedTitleLength <= 50;

  useEffect(() => {
    isMountedRef.current = true;
    const dialog = dialogRef.current;

    if (dialog !== null && !dialog.open) {
      dialog.showModal();
    }

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  function closeDialog(): void {
    if (!isSavingRef.current) {
      dialogRef.current?.close();
    }
  }

  function handleBackdropPointerDown(event: PointerEvent<HTMLDialogElement>): void {
    if (event.target === event.currentTarget) {
      closeDialog();
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isSavingRef.current || !canSave) {
      return;
    }

    isSavingRef.current = true;
    setSaveError(null);
    setIsSaving(true);

    const normalizedDescription = description.trim();

    try {
      await onSave({
        title: title.trim(),
        description: normalizedDescription.length === 0 ? null : normalizedDescription,
        isPublic,
      });
      if (isMountedRef.current) {
        dialogRef.current?.close();
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
    <dialog
      aria-busy={isSaving}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      aria-modal="true"
      className={styles.cardEditorDialog}
      data-deck-creator="new"
      onCancel={(event) => {
        if (isSavingRef.current) {
          event.preventDefault();
        }
      }}
      onClose={onClose}
      onPointerDown={handleBackdropPointerDown}
      ref={dialogRef}
    >
      <div className={styles.cardEditorShell}>
        <span aria-hidden="true" className={styles.cardEditorGlow} />
        <header className={styles.cardEditorHeader}>
          <div className={styles.cardEditorHeading}>
            <span aria-hidden="true" className={styles.cardEditorMark}>
              <DeckCreatorGlyph name="deck" />
            </span>
            <div>
              <span className={styles.cardEditorEyebrow}>{messages.eyebrow}</span>
              <h2 id={titleId}>{messages.title}</h2>
              <p id={descriptionId}>{messages.description}</p>
            </div>
          </div>
          <button
            aria-label={messages.close}
            className={styles.cardEditorClose}
            disabled={isSaving}
            onClick={closeDialog}
            type="button"
          >
            <DeckCreatorGlyph name="close" />
          </button>
        </header>

        <form className={styles.cardEditorForm} onSubmit={handleSubmit}>
          <label className={styles.cardEditorField} htmlFor={deckTitleId}>
            <span className={styles.cardEditorLabel}>
              <strong>
                {messages.deckTitle} <span aria-hidden="true">*</span>
              </strong>
              <code>title</code>
            </span>
            <input
              autoComplete="off"
              autoFocus
              id={deckTitleId}
              maxLength={50}
              minLength={3}
              name="title"
              onChange={(event) => setTitle(event.currentTarget.value)}
              required
              value={title}
            />
            <small>{title.length}/50</small>
          </label>

          <label className={styles.cardEditorField} htmlFor={deckDescriptionId}>
            <span className={styles.cardEditorLabel}>
              <strong>{messages.deckDescription}</strong>
              <span className={styles.deckCreatorOptional}>{messages.optional}</span>
              <code>description</code>
            </span>
            <textarea
              id={deckDescriptionId}
              maxLength={3000}
              name="description"
              onChange={(event) => setDescription(event.currentTarget.value)}
              placeholder={messages.descriptionPlaceholder}
              rows={3}
              value={description}
            />
          </label>

          <fieldset aria-labelledby={privacyLegendId} className={styles.deckCreatorPrivacy}>
            <legend id={privacyLegendId}>
              <strong>{messages.privacy}</strong>
              <code>is_public</code>
            </legend>
            <div className={styles.deckCreatorPrivacyOptions}>
              <label className={styles.deckCreatorPrivacyOption} htmlFor={privateId}>
                <input
                  checked={!isPublic}
                  id={privateId}
                  name="is_public"
                  onChange={() => setIsPublic(false)}
                  type="radio"
                  value="false"
                />
                <span>
                  <strong>{messages.private}</strong>
                  <small>{messages.privateDescription}</small>
                </span>
              </label>
              <label className={styles.deckCreatorPrivacyOption} htmlFor={publicId}>
                <input
                  checked={isPublic}
                  id={publicId}
                  name="is_public"
                  onChange={() => setIsPublic(true)}
                  type="radio"
                  value="true"
                />
                <span>
                  <strong>{messages.public}</strong>
                  <small>{messages.publicDescription}</small>
                </span>
              </label>
            </div>
          </fieldset>

          {saveError === null ? null : (
            <p className={styles.cardEditorError} role="alert">
              {getDeckCreateErrorMessage(saveError, messages)}
            </p>
          )}

          <footer className={styles.cardEditorFooter}>
            <p>{messages.footer}</p>
            <div className={styles.cardEditorButtons}>
              <button
                className={styles.cardEditorCancel}
                disabled={isSaving}
                onClick={closeDialog}
                type="button"
              >
                {messages.cancel}
              </button>
              <button
                className={styles.cardEditorSave}
                disabled={isSaving || !canSave}
                type="submit"
              >
                {isSaving ? (
                  <span aria-hidden="true" className={styles.cardEditorSpinner} />
                ) : (
                  <DeckCreatorGlyph name="save" />
                )}
                <span>{isSaving ? messages.creating : messages.create}</span>
              </button>
            </div>
          </footer>
        </form>
      </div>
    </dialog>
  );
}
