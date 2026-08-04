import { useEffect, useId, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { isApiError } from "../../api";
import type { CreateLibraryDeckInput } from "../../features/library/model/library-types";
import styles from "./LibraryPage.module.css";

interface DeckCreatorDialogProps {
  onClose: () => void;
  onSave: (input: CreateLibraryDeckInput) => Promise<void>;
}

function getDeckCreateErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось создать колоду. Попробуйте ещё раз.";
  }
  if (error.status === 403) {
    return "У вас нет доступа к созданию колод.";
  }
  if (error.status === 409) {
    return "Сервер отклонил новую колоду. Попробуйте изменить название.";
  }
  if (error.status === 422) {
    return "Проверьте название и остальные поля колоды.";
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return "Сервер вернул неожиданный ответ после создания колоды.";
  }
  if (error.code === "REQUEST_ABORTED") {
    return "Создание колоды было отменено.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может создать колоду.";
  }

  return "Не удалось создать колоду. Попробуйте ещё раз.";
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
              <span className={styles.cardEditorEyebrow}>Новая коллекция</span>
              <h2 id={titleId}>Новая колода</h2>
              <p id={descriptionId}>Задайте название, описание и уровень приватности.</p>
            </div>
          </div>
          <button
            aria-label="Закрыть окно создания колоды"
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
                Название <span aria-hidden="true">*</span>
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
              <strong>Описание</strong>
              <span className={styles.deckCreatorOptional}>необязательно</span>
              <code>description</code>
            </span>
            <textarea
              id={deckDescriptionId}
              maxLength={3000}
              name="description"
              onChange={(event) => setDescription(event.currentTarget.value)}
              placeholder="О чём эта колода?"
              rows={3}
              value={description}
            />
          </label>

          <fieldset aria-labelledby={privacyLegendId} className={styles.deckCreatorPrivacy}>
            <legend id={privacyLegendId}>
              <strong>Приватность</strong>
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
                  <strong>Приватная</strong>
                  <small>Не публикуется в общем доступе</small>
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
                  <strong>Публичная</strong>
                  <small>Появляется в публичной библиотеке</small>
                </span>
              </label>
            </div>
          </fieldset>

          {saveError === null ? null : (
            <p className={styles.cardEditorError} role="alert">
              {getDeckCreateErrorMessage(saveError)}
            </p>
          )}

          <footer className={styles.cardEditorFooter}>
            <p>Новая колода появится первой в вашей библиотеке.</p>
            <div className={styles.cardEditorButtons}>
              <button
                className={styles.cardEditorCancel}
                disabled={isSaving}
                onClick={closeDialog}
                type="button"
              >
                Отмена
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
                <span>{isSaving ? "Создаём…" : "Создать"}</span>
              </button>
            </div>
          </footer>
        </form>
      </div>
    </dialog>
  );
}
