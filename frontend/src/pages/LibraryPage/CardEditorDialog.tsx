import { useEffect, useId, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { isApiError } from "../../api";
import type {
  EditableLibraryCard,
  UpdateLibraryCardInput,
} from "../../features/library/model/library-types";
import styles from "./LibraryPage.module.css";

interface CardEditorDialogProps {
  card: EditableLibraryCard | null;
  onClose: () => void;
  onSave: (input: UpdateLibraryCardInput) => Promise<void>;
}

function getCardSaveErrorMessage(error: unknown, isCreating: boolean): string {
  const action = isCreating ? "создать" : "сохранить";

  if (!isApiError(error)) {
    return `Не удалось ${action} карточку. Попробуйте ещё раз.`;
  }
  if (error.status === 403) {
    return isCreating
      ? "У вас нет доступа к созданию карточек."
      : "У вас нет доступа к редактированию этой карточки.";
  }
  if (error.status === 404) {
    return "Карточка больше не найдена.";
  }
  if (error.status === 409) {
    return "Сервер отклонил изменения. Проверьте значения полей.";
  }
  if (error.status === 422) {
    return "Проверьте длину и формат заполненных полей.";
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return `Сервер вернул неожиданный ответ после попытки ${isCreating ? "создания" : "сохранения"}.`;
  }
  if (error.code === "REQUEST_ABORTED") {
    return "Сохранение было отменено.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return `Сервер временно не может ${action} карточку.`;
  }

  return `Не удалось ${action} карточку. Попробуйте ещё раз.`;
}

function EditorGlyph({ name }: { name: "close" | "save" }) {
  if (name === "close") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="m7 7 10 10M17 7 7 17" />
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

export function CardEditorDialog({ card, onClose, onSave }: CardEditorDialogProps) {
  const isCreating = card === null;
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const isMountedRef = useRef(true);
  const isSavingRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();
  const frontTextId = useId();
  const backTextId = useId();
  const frontLangId = useId();
  const backLangId = useId();
  const [frontText, setFrontText] = useState(card?.frontText ?? "");
  const [backText, setBackText] = useState(card?.backText ?? "");
  const [frontLang, setFrontLang] = useState(card?.frontLang ?? "");
  const [backLang, setBackLang] = useState(card?.backLang ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown | null>(null);
  const hasChanges =
    card === null ||
    frontText !== card.frontText ||
    backText !== card.backText ||
    frontLang !== card.frontLang ||
    backLang !== card.backLang;
  const hasRequiredTexts = [frontText, backText].every((value) => value.trim().length > 0);
  const hasValidLanguages = [frontLang, backLang].every((value) => {
    const length = value.trim().length;
    return length >= 2 && length <= 3;
  });
  const canSave = hasChanges && hasRequiredTexts && hasValidLanguages;

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

    try {
      await onSave({ frontText, backText, frontLang, backLang });
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
      data-card-editor={card?.uuid ?? "new"}
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
              <CardActionPencil />
            </span>
            <div>
              <span className={styles.cardEditorEyebrow}>Настройка карточки</span>
              <h2 id={titleId}>{isCreating ? "Новая карточка" : "Редактировать карточку"}</h2>
              <p id={descriptionId}>
                {isCreating
                  ? "Заполните тексты и языки обеих сторон."
                  : "Измените тексты и языки обеих сторон."}
              </p>
            </div>
          </div>
          <button
            aria-label={isCreating ? "Закрыть окно создания" : "Закрыть окно редактирования"}
            className={styles.cardEditorClose}
            disabled={isSaving}
            onClick={closeDialog}
            type="button"
          >
            <EditorGlyph name="close" />
          </button>
        </header>

        <form className={styles.cardEditorForm} onSubmit={handleSubmit}>
          <div className={styles.cardEditorTextGrid}>
            <label className={styles.cardEditorField} htmlFor={backTextId}>
              <span className={styles.cardEditorLabel}>
                <strong>
                  Иностранное слово <span aria-hidden="true">*</span>
                </strong>
                <code>back_text</code>
              </span>
              <textarea
                autoFocus
                id={backTextId}
                maxLength={255}
                name="back_text"
                onChange={(event) => setBackText(event.currentTarget.value)}
                required
                rows={3}
                value={backText}
              />
              <small>{backText.length}/255</small>
            </label>

            <label className={styles.cardEditorField} htmlFor={frontTextId}>
              <span className={styles.cardEditorLabel}>
                <strong>
                  Перевод <span aria-hidden="true">*</span>
                </strong>
                <code>front_text</code>
              </span>
              <textarea
                id={frontTextId}
                maxLength={255}
                name="front_text"
                onChange={(event) => setFrontText(event.currentTarget.value)}
                required
                rows={3}
                value={frontText}
              />
              <small>{frontText.length}/255</small>
            </label>
          </div>

          <div className={styles.cardEditorLanguageGrid}>
            <label className={styles.cardEditorField} htmlFor={backLangId}>
              <span className={styles.cardEditorLabel}>
                <strong>
                  Язык слова <span aria-hidden="true">*</span>
                </strong>
                <code>back_lang</code>
              </span>
              <input
                autoCapitalize="none"
                autoComplete="off"
                id={backLangId}
                maxLength={3}
                minLength={2}
                name="back_lang"
                onChange={(event) => setBackLang(event.currentTarget.value)}
                required
                spellCheck={false}
                value={backLang}
              />
            </label>

            <label className={styles.cardEditorField} htmlFor={frontLangId}>
              <span className={styles.cardEditorLabel}>
                <strong>
                  Язык перевода <span aria-hidden="true">*</span>
                </strong>
                <code>front_lang</code>
              </span>
              <input
                autoCapitalize="none"
                autoComplete="off"
                id={frontLangId}
                maxLength={3}
                minLength={2}
                name="front_lang"
                onChange={(event) => setFrontLang(event.currentTarget.value)}
                required
                spellCheck={false}
                value={frontLang}
              />
            </label>
          </div>

          {saveError === null ? null : (
            <p className={styles.cardEditorError} role="alert">
              {getCardSaveErrorMessage(saveError, isCreating)}
            </p>
          )}

          <footer className={styles.cardEditorFooter}>
            <p>
              {isCreating
                ? "Карточка появится в библиотеке после создания."
                : "Изменения применятся к карточке сразу после сохранения."}
            </p>
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
                  <EditorGlyph name="save" />
                )}
                <span>
                  {isSaving
                    ? isCreating
                      ? "Создаём…"
                      : "Сохраняем…"
                    : isCreating
                      ? "Создать"
                      : "Сохранить"}
                </span>
              </button>
            </div>
          </footer>
        </form>
      </div>
    </dialog>
  );
}

function CardActionPencil() {
  return (
    <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path d="m4 20 4.2-1 10.9-10.9a2.2 2.2 0 0 0-3.1-3.1L5.1 15.9 4 20Z" />
      <path d="m14.7 6.3 3 3" />
    </svg>
  );
}
