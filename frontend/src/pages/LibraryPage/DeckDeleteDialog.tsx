import { useEffect, useId, useRef, type FormEvent, type PointerEvent } from "react";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import styles from "./LibraryPage.module.css";

const MESSAGES = defineMessages(
  {
    eyebrow: "Удаление колоды",
    title: "Удалить колоду?",
    description: "Колода исчезнет из вашей библиотеки.",
    warning: "Это действие нельзя отменить.",
    cancel: "Отмена",
    confirm: "Удалить",
  },
  {
    eyebrow: "Delete deck",
    title: "Delete this deck?",
    description: "The deck will disappear from your library.",
    warning: "This action cannot be undone.",
    cancel: "Cancel",
    confirm: "Delete",
  },
);

interface DeckDeleteDialogProps {
  deckTitle: string;
  onClose: () => void;
  onConfirm: () => void;
}

function DeleteGlyph() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      viewBox="0 0 24 24"
    >
      <path d="M5 7h14M9 7V4.8h6V7M7.2 7l.8 13h8l.8-13M10 11v5M14 11v5" />
    </svg>
  );
}

export function DeckDeleteDialog({ deckTitle, onClose, onConfirm }: DeckDeleteDialogProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;

    if (dialog !== null && !dialog.open) {
      dialog.showModal();
    }
  }, []);

  function closeDialog(): void {
    dialogRef.current?.close();
  }

  function handleBackdropPointerDown(event: PointerEvent<HTMLDialogElement>): void {
    if (event.target === event.currentTarget) {
      closeDialog();
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    closeDialog();
    onConfirm();
  }

  return (
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      aria-modal="true"
      className={styles.deckDeleteDialog}
      data-deck-delete-dialog="true"
      onClose={onClose}
      onPointerDown={handleBackdropPointerDown}
      ref={dialogRef}
    >
      <form className={styles.deckDeleteShell} onSubmit={handleSubmit}>
        <header className={styles.deckDeleteHeader}>
          <span aria-hidden="true" className={styles.deckDeleteMark}>
            <DeleteGlyph />
          </span>
          <div>
            <span className={styles.deckDeleteEyebrow}>{messages.eyebrow}</span>
            <h2 id={titleId}>{messages.title}</h2>
          </div>
        </header>

        <div className={styles.deckDeleteBody}>
          <p id={descriptionId}>{messages.description}</p>
          <strong className={styles.deckDeleteName}>{deckTitle}</strong>
          <p className={styles.deckDeleteWarning}>{messages.warning}</p>
        </div>

        <footer className={styles.deckDeleteActions}>
          <button autoFocus className={styles.deckDeleteCancel} onClick={closeDialog} type="button">
            {messages.cancel}
          </button>
          <button className={styles.deckDeleteConfirm} type="submit">
            <DeleteGlyph />
            <span>{messages.confirm}</span>
          </button>
        </footer>
      </form>
    </dialog>
  );
}
