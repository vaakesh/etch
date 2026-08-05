import { useEffect, useId, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { isApiError } from "../../api";
import type {
  EditableLibraryCard,
  UpdateLibraryCardInput,
} from "../../features/library/model/library-types";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import styles from "./LibraryPage.module.css";

const MESSAGES = defineMessages(
  {
    errors: {
      genericCreate: "Не удалось создать карточку. Попробуйте ещё раз.",
      genericSave: "Не удалось сохранить карточку. Попробуйте ещё раз.",
      forbiddenCreate: "У вас нет доступа к созданию карточек.",
      forbiddenSave: "У вас нет доступа к редактированию этой карточки.",
      notFound: "Карточка больше не найдена.",
      conflict: "Сервер отклонил изменения. Проверьте значения полей.",
      validation: "Проверьте длину и формат заполненных полей.",
      invalidCreate: "Сервер вернул неожиданный ответ после попытки создания.",
      invalidSave: "Сервер вернул неожиданный ответ после попытки сохранения.",
      aborted: "Сохранение было отменено.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      serverCreate: "Сервер временно не может создать карточку.",
      serverSave: "Сервер временно не может сохранить карточку.",
    },
    eyebrow: "Настройка карточки",
    newTitle: "Новая карточка",
    editTitle: "Редактировать карточку",
    newDescription: "Заполните тексты и языки обеих сторон.",
    editDescription: "Измените тексты и языки обеих сторон.",
    closeCreate: "Закрыть окно создания",
    closeEdit: "Закрыть окно редактирования",
    foreignWord: "Иностранное слово",
    translation: "Перевод",
    wordLanguage: "Язык слова",
    translationLanguage: "Язык перевода",
    createFooter: "Карточка появится в библиотеке после создания.",
    editFooter: "Изменения применятся к карточке сразу после сохранения.",
    cancel: "Отмена",
    creating: "Создаём…",
    saving: "Сохраняем…",
    create: "Создать",
    save: "Сохранить",
  },
  {
    errors: {
      genericCreate: "We couldn't create the card. Try again.",
      genericSave: "We couldn't save the card. Try again.",
      forbiddenCreate: "You do not have permission to create cards.",
      forbiddenSave: "You do not have permission to edit this card.",
      notFound: "This card could not be found.",
      conflict: "The server rejected the changes. Check the field values.",
      validation: "Check the length and format of each field.",
      invalidCreate: "The server returned an unexpected response after creating the card.",
      invalidSave: "The server returned an unexpected response after saving the card.",
      aborted: "Saving was canceled.",
      network: "We couldn't reach the server. Check your connection.",
      serverCreate: "The server cannot create the card right now.",
      serverSave: "The server cannot save the card right now.",
    },
    eyebrow: "Card settings",
    newTitle: "New card",
    editTitle: "Edit card",
    newDescription: "Enter the text and language for both sides.",
    editDescription: "Update the text and language for both sides.",
    closeCreate: "Close new card dialog",
    closeEdit: "Close card editor",
    foreignWord: "Foreign word",
    translation: "Translation",
    wordLanguage: "Word language",
    translationLanguage: "Translation language",
    createFooter: "The card will appear in your library after it is created.",
    editFooter: "Your changes will be applied as soon as the card is saved.",
    cancel: "Cancel",
    creating: "Creating…",
    saving: "Saving…",
    create: "Create",
    save: "Save",
  },
);

interface CardEditorDialogProps {
  card: EditableLibraryCard | null;
  onClose: () => void;
  onSave: (input: UpdateLibraryCardInput) => Promise<void>;
}

function getCardSaveErrorMessage(
  error: unknown,
  isCreating: boolean,
  messages: (typeof MESSAGES)["ru-RU"],
): string {
  const genericMessage = isCreating ? messages.errors.genericCreate : messages.errors.genericSave;

  if (!isApiError(error)) {
    return genericMessage;
  }
  if (error.status === 403) {
    return isCreating ? messages.errors.forbiddenCreate : messages.errors.forbiddenSave;
  }
  if (error.status === 404) {
    return messages.errors.notFound;
  }
  if (error.status === 409) {
    return messages.errors.conflict;
  }
  if (error.status === 422) {
    return messages.errors.validation;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return isCreating ? messages.errors.invalidCreate : messages.errors.invalidSave;
  }
  if (error.code === "REQUEST_ABORTED") {
    return messages.errors.aborted;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return isCreating ? messages.errors.serverCreate : messages.errors.serverSave;
  }

  return genericMessage;
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
  const messages = useLocalizedMessages(MESSAGES);
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
              <span className={styles.cardEditorEyebrow}>{messages.eyebrow}</span>
              <h2 id={titleId}>{isCreating ? messages.newTitle : messages.editTitle}</h2>
              <p id={descriptionId}>
                {isCreating ? messages.newDescription : messages.editDescription}
              </p>
            </div>
          </div>
          <button
            aria-label={isCreating ? messages.closeCreate : messages.closeEdit}
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
                  {messages.foreignWord} <span aria-hidden="true">*</span>
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
                  {messages.translation} <span aria-hidden="true">*</span>
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
                  {messages.wordLanguage} <span aria-hidden="true">*</span>
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
                  {messages.translationLanguage} <span aria-hidden="true">*</span>
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
              {getCardSaveErrorMessage(saveError, isCreating, messages)}
            </p>
          )}

          <footer className={styles.cardEditorFooter}>
            <p>{isCreating ? messages.createFooter : messages.editFooter}</p>
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
                  <EditorGlyph name="save" />
                )}
                <span>
                  {isSaving
                    ? isCreating
                      ? messages.creating
                      : messages.saving
                    : isCreating
                      ? messages.create
                      : messages.save}
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
