import { useEffect, useId, useRef, type FormEvent, type PointerEvent } from "react";
import styles from "./LibraryPage.module.css";

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
            <span className={styles.deckDeleteEyebrow}>Удаление колоды</span>
            <h2 id={titleId}>Удалить колоду?</h2>
          </div>
        </header>

        <div className={styles.deckDeleteBody}>
          <p id={descriptionId}>Колода исчезнет из вашей библиотеки.</p>
          <strong className={styles.deckDeleteName}>{deckTitle}</strong>
          <p className={styles.deckDeleteWarning}>Это действие нельзя отменить.</p>
        </div>

        <footer className={styles.deckDeleteActions}>
          <button autoFocus className={styles.deckDeleteCancel} onClick={closeDialog} type="button">
            Отмена
          </button>
          <button className={styles.deckDeleteConfirm} type="submit">
            <DeleteGlyph />
            <span>Удалить</span>
          </button>
        </footer>
      </form>
    </dialog>
  );
}
