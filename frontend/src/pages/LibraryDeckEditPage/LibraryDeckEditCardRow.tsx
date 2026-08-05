import { useEffect, useId, useRef, useState } from "react";
import { isApiError } from "../../api";
import type {
  EditableLibraryCard,
  UpdateLibraryCardInput,
} from "../../features/library/model/library-types";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import { CardEditorDialog } from "../LibraryPage/CardEditorDialog";
import libraryStyles from "../LibraryPage/LibraryPage.module.css";
import { OverflowingCardText } from "../LibraryPage/OverflowingCardText";

interface LibraryDeckEditCardRowProps {
  card: EditableLibraryCard;
  onRemove: (cardUuid: string) => Promise<void>;
  onUpdate: (cardUuid: string, input: UpdateLibraryCardInput) => Promise<void>;
}

const MESSAGES = defineMessages(
  {
    removeErrors: {
      default: "Не удалось удалить карточку из колоды. Попробуйте ещё раз.",
      notFound: "Колода или карточка больше недоступна.",
      aborted: "Удаление карточки из колоды было отменено.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      server: "Сервер временно не может изменить колоду.",
    },
    actionsLabel: (card: string) => `Действия с карточкой «${card}»`,
    actions: "Действия",
    edit: "Редактировать",
    removeTitle: "Удалить карточку только из этой колоды",
    removing: "Удаляем…",
    remove: "Удалить из колоды",
    word: "Слово",
    translation: "Перевод",
  },
  {
    removeErrors: {
      default: "Couldn't remove the card from the deck. Please try again.",
      notFound: "The deck or card is no longer available.",
      aborted: "Removing the card from the deck was canceled.",
      network: "Couldn't reach the server. Check your connection.",
      server: "The server can't update the deck right now.",
    },
    actionsLabel: (card: string) => `Actions for card “${card}”`,
    actions: "Actions",
    edit: "Edit",
    removeTitle: "Remove this card from this deck only",
    removing: "Removing…",
    remove: "Remove from deck",
    word: "Word",
    translation: "Translation",
  },
);

type CardRemoveErrorMessages = (typeof MESSAGES)["ru-RU"]["removeErrors"];

function getCardRemoveErrorMessage(error: unknown, messages: CardRemoveErrorMessages): string {
  if (!isApiError(error)) {
    return messages.default;
  }
  if (error.status === 403 || error.status === 404) {
    return messages.notFound;
  }
  if (error.code === "REQUEST_ABORTED") {
    return messages.aborted;
  }
  if (error.status === 0) {
    return messages.network;
  }
  if (error.status >= 500) {
    return messages.server;
  }

  return messages.default;
}

function CardActionGlyph({ name }: { name: "delete" | "edit" | "menu" }) {
  if (name === "menu") {
    return (
      <svg aria-hidden="true" fill="currentColor" viewBox="0 0 24 24">
        <circle cx="5" cy="12" r="1.7" />
        <circle cx="12" cy="12" r="1.7" />
        <circle cx="19" cy="12" r="1.7" />
      </svg>
    );
  }

  if (name === "edit") {
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
        <path d="m4 20 4.2-1 10.9-10.9a2.2 2.2 0 0 0-3.1-3.1L5.1 15.9 4 20Z" />
        <path d="m14.7 6.3 3 3" />
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
      <path d="M5 7h14M9 7V4.8h6V7M7.2 7l.8 13h8l.8-13M10 11v5M14 11v5" />
    </svg>
  );
}

function CardActions({
  card,
  isRemoving,
  onEdit,
  onRemove,
}: {
  card: EditableLibraryCard;
  isRemoving: boolean;
  onEdit: () => void;
  onRemove: () => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const menuId = useId();
  const triggerId = useId();
  const menuRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  function positionMenu(): void {
    const menu = menuRef.current;
    const trigger = triggerRef.current;

    if (menu === null || trigger === null) {
      return;
    }

    const triggerRect = trigger.getBoundingClientRect();
    const viewportPadding = 12;
    const menuWidth = Math.min(216, window.innerWidth - viewportPadding * 2);
    const estimatedMenuHeight = 105;
    const left = Math.min(
      Math.max(viewportPadding, triggerRect.right - menuWidth),
      window.innerWidth - menuWidth - viewportPadding,
    );
    const hasRoomBelow =
      triggerRect.bottom + estimatedMenuHeight + viewportPadding <= window.innerHeight;
    const top = hasRoomBelow
      ? triggerRect.bottom + 7
      : Math.max(viewportPadding, triggerRect.top - estimatedMenuHeight - 7);

    menu.style.setProperty("--card-actions-menu-left", `${left}px`);
    menu.style.setProperty("--card-actions-menu-top", `${top}px`);
    menu.style.setProperty("--card-actions-menu-width", `${menuWidth}px`);
    menu.style.setProperty(
      "--card-actions-menu-origin",
      hasRoomBelow ? "top right" : "bottom right",
    );
  }

  return (
    <div className={libraryStyles.cardActions}>
      <button
        aria-label={messages.actionsLabel(card.backText)}
        className={libraryStyles.cardActionsTrigger}
        data-card-actions-trigger="true"
        id={triggerId}
        onClick={positionMenu}
        popoverTarget={menuId}
        popoverTargetAction="toggle"
        ref={triggerRef}
        title={messages.actions}
        type="button"
      >
        <CardActionGlyph name="menu" />
      </button>
      <div
        aria-labelledby={triggerId}
        className={libraryStyles.cardActionsMenu}
        id={menuId}
        popover="auto"
        ref={menuRef}
        role="group"
      >
        <button
          className={libraryStyles.cardEditAction}
          data-card-action="edit"
          disabled={isRemoving}
          onClick={() => {
            menuRef.current?.hidePopover();
            onEdit();
          }}
          type="button"
        >
          <CardActionGlyph name="edit" />
          <span>{messages.edit}</span>
        </button>
        <span aria-hidden="true" className={libraryStyles.cardActionsDivider} />
        <button
          className={libraryStyles.cardDeleteAction}
          data-card-action="remove-from-deck"
          disabled={isRemoving}
          onClick={() => {
            menuRef.current?.hidePopover();
            onRemove();
          }}
          title={messages.removeTitle}
          type="button"
        >
          <CardActionGlyph name="delete" />
          <span>{isRemoving ? messages.removing : messages.remove}</span>
        </button>
      </div>
    </div>
  );
}

export function LibraryDeckEditCardRow({ card, onRemove, onUpdate }: LibraryDeckEditCardRowProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const isMountedRef = useRef(true);
  const removeInFlightRef = useRef(false);
  const rowRef = useRef<HTMLLIElement | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<unknown | null>(null);
  const cardRowClassName = isRemoving
    ? `${libraryStyles.cardRow} ${libraryStyles.cardRowDeleting}`
    : libraryStyles.cardRow;

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  async function handleRemove(): Promise<void> {
    if (removeInFlightRef.current) {
      return;
    }

    removeInFlightRef.current = true;
    setRemoveError(null);
    setIsRemoving(true);
    const row = rowRef.current;
    const nextFocusTarget =
      row?.nextElementSibling?.querySelector<HTMLButtonElement>(
        'button[data-card-actions-trigger="true"]',
      ) ??
      row?.previousElementSibling?.querySelector<HTMLButtonElement>(
        'button[data-card-actions-trigger="true"]',
      ) ??
      document.getElementById("deck-cards-heading");

    try {
      await onRemove(card.uuid);
      if (nextFocusTarget !== null) {
        requestAnimationFrame(() => {
          if (nextFocusTarget.isConnected) {
            nextFocusTarget.focus();
          }
        });
      }
    } catch (error: unknown) {
      if (isMountedRef.current && (!isApiError(error) || error.code !== "REQUEST_ABORTED")) {
        setRemoveError(error);
      }
    } finally {
      removeInFlightRef.current = false;
      if (isMountedRef.current) {
        setIsRemoving(false);
      }
    }
  }

  return (
    <li aria-busy={isRemoving} className={cardRowClassName} data-card-uuid={card.uuid} ref={rowRef}>
      <div className={`${libraryStyles.cardFace} ${libraryStyles.cardFaceSource}`}>
        <span className={libraryStyles.languageBadge}>{card.backLang.toUpperCase()}</span>
        <div className={libraryStyles.cardFaceCopy}>
          <OverflowingCardText
            className={libraryStyles.cardWord}
            label={messages.word}
            language={card.backLang}
            text={card.backText}
          />
        </div>
      </div>

      <div className={`${libraryStyles.cardFace} ${libraryStyles.cardFaceTarget}`}>
        <span className={libraryStyles.languageBadge}>{card.frontLang.toUpperCase()}</span>
        <div className={libraryStyles.cardFaceCopy}>
          <OverflowingCardText
            className={libraryStyles.cardTranslation}
            label={messages.translation}
            language={card.frontLang}
            text={card.frontText}
          />
        </div>
      </div>

      <CardActions
        card={card}
        isRemoving={isRemoving}
        onEdit={() => setIsEditorOpen(true)}
        onRemove={() => void handleRemove()}
      />
      {removeError === null ? null : (
        <p className={libraryStyles.cardMutationError} role="alert">
          {getCardRemoveErrorMessage(removeError, messages.removeErrors)}
        </p>
      )}
      {isEditorOpen ? (
        <CardEditorDialog
          card={card}
          onClose={() => setIsEditorOpen(false)}
          onSave={(input) => onUpdate(card.uuid, input)}
        />
      ) : null}
    </li>
  );
}
