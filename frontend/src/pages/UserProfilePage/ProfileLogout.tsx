import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent,
  type SyntheticEvent,
} from "react";
import { useAuth } from "../../auth/hooks/useAuth";
import { DashboardIcon } from "../../components/DashboardVisuals";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import styles from "./ProfileLogout.module.css";

const MESSAGES = defineMessages(
  {
    logout: "Выйти",
    logoutEyebrow: "Аккаунт",
    logoutTitle: "Выйти из Etch?",
    logoutDescription:
      "Сессия на этом устройстве завершится. Ваши колоды и прогресс останутся на месте.",
    logoutCancel: "Остаться",
    logoutConfirm: "Выйти",
    logoutPending: "Выходим…",
  },
  {
    logout: "Sign out",
    logoutEyebrow: "Account",
    logoutTitle: "Sign out of Etch?",
    logoutDescription:
      "Your session on this device will end. Your decks and progress will stay right where they are.",
    logoutCancel: "Stay signed in",
    logoutConfirm: "Sign out",
    logoutPending: "Signing out…",
  },
);

interface LogoutDialogProps {
  isPending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function LogoutDialog({ isPending, onClose, onConfirm }: LogoutDialogProps) {
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
    if (!isPending) {
      dialogRef.current?.close();
    }
  }

  function handleBackdropPointerDown(event: PointerEvent<HTMLDialogElement>): void {
    if (event.target === event.currentTarget) {
      closeDialog();
    }
  }

  function handleCancel(event: SyntheticEvent<HTMLDialogElement>): void {
    if (isPending) {
      event.preventDefault();
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onConfirm();
  }

  return (
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      aria-modal="true"
      className={styles.logoutDialog}
      onCancel={handleCancel}
      onClose={onClose}
      onPointerDown={handleBackdropPointerDown}
      ref={dialogRef}
    >
      <form className={styles.logoutDialogShell} onSubmit={handleSubmit}>
        <div className={styles.logoutDialogBody}>
          <span aria-hidden="true" className={styles.logoutDialogMark}>
            <DashboardIcon name="logout" />
          </span>
          <span className={styles.logoutDialogEyebrow}>{messages.logoutEyebrow}</span>
          <h2 id={titleId}>{messages.logoutTitle}</h2>
          <p id={descriptionId}>{messages.logoutDescription}</p>
        </div>

        <div className={styles.logoutDialogActions}>
          <button
            autoFocus
            className={styles.logoutDialogCancel}
            disabled={isPending}
            onClick={closeDialog}
            type="button"
          >
            {messages.logoutCancel}
          </button>
          <button className={styles.logoutDialogConfirm} disabled={isPending} type="submit">
            {isPending ? messages.logoutPending : messages.logoutConfirm}
          </button>
        </div>
      </form>
    </dialog>
  );
}

export function ProfileLogout() {
  const messages = useLocalizedMessages(MESSAGES);
  const { logout } = useAuth();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isPending, setIsPending] = useState(false);

  function handleLogout(): void {
    setIsPending(true);
    void logout().catch(() => {
      setIsPending(false);
    });
  }

  return (
    <div className={styles.actions}>
      <button
        aria-haspopup="dialog"
        className={styles.logoutButton}
        onClick={() => setIsDialogOpen(true)}
        type="button"
      >
        <DashboardIcon className={styles.logoutIcon} name="logout" />
        <span className={styles.logoutLabel}>{messages.logout}</span>
      </button>
      {isDialogOpen ? (
        <LogoutDialog
          isPending={isPending}
          onClose={() => setIsDialogOpen(false)}
          onConfirm={handleLogout}
        />
      ) : null}
    </div>
  );
}
