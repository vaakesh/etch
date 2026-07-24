import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { isApiError } from "../../api";
import { useAuth } from "../../auth/hooks/useAuth";
import { DashboardIcon } from "../../components/DashboardVisuals";
import type {
  LibraryCard,
  LibraryDeckItem,
  UpdateLibraryCardInput,
} from "../../features/library/model/library-types";
import {
  useLibraryCards,
  type UseLibraryCardsResult,
} from "../../features/library/model/useLibraryCards";
import { useLibraryDecks } from "../../features/library/model/useLibraryDecks";
import { AddCardToDeckDialog } from "./AddCardToDeckDialog";
import { CardEditorDialog } from "./CardEditorDialog";
import { DeckCreatorDialog } from "./DeckCreatorDialog";
import styles from "./LibraryPage.module.css";

type LibraryView = "decks" | "cards";

const numberFormatter = new Intl.NumberFormat("ru-RU");
const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

function formatUpdatedAt(value: string | null): string {
  if (value === null) {
    return "Не обновлялась";
  }

  return dateFormatter.format(new Date(value));
}

function getLibraryErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось загрузить библиотеку. Попробуйте ещё раз.";
  }
  if (error.status === 403) {
    return "У этой учётной записи нет доступа к библиотеке.";
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return "Сервер вернул данные библиотеки в неожиданном формате.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может загрузить библиотеку.";
  }

  return "Не удалось загрузить библиотеку. Попробуйте ещё раз.";
}

function getLibraryCardsErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось загрузить карточки. Попробуйте ещё раз.";
  }
  if (error.status === 403) {
    return "У этой учётной записи нет доступа к карточкам.";
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

  return "Не удалось загрузить карточки. Попробуйте ещё раз.";
}

function getCardDeleteErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось удалить карточку. Попробуйте ещё раз.";
  }
  if (error.status === 403) {
    return "У вас нет доступа к удалению этой карточки.";
  }
  if (error.status === 404) {
    return "Карточка уже удалена или больше не существует.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может удалить карточку.";
  }

  return "Не удалось удалить карточку. Попробуйте ещё раз.";
}

function getFavouriteErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 403) {
      return "Нет доступа к изменению этой колоды.";
    }
    if (error.status === 404) {
      return "Колода больше не найдена.";
    }
  }

  return "Не удалось изменить избранное. Попробуйте ещё раз.";
}

function Glyph({ name }: { name: "heart" | "pencil" | "play" | "sparkles" }) {
  if (name === "heart") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        viewBox="0 0 24 24"
      >
        <path d="M20.8 5.8a5.4 5.4 0 0 0-7.7 0L12 7l-1.1-1.2a5.4 5.4 0 0 0-7.7 7.7L12 22l8.8-8.5a5.4 5.4 0 0 0 0-7.7Z" />
      </svg>
    );
  }
  if (name === "pencil") {
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
        <path d="m4 20 4.2-1 11-11a2.1 2.1 0 0 0-3-3l-11 11z" />
        <path d="m14.8 6.5 3 3M4 20l3-3" />
      </svg>
    );
  }
  if (name === "play") {
    return (
      <svg aria-hidden="true" fill="currentColor" viewBox="0 0 24 24">
        <path d="M8.2 5.6c0-1.1 1.2-1.8 2.1-1.2l9 5.4a2.5 2.5 0 0 1 0 4.3l-9 5.4c-.9.6-2.1-.1-2.1-1.2Z" />
      </svg>
    );
  }

  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeWidth="1.6"
      viewBox="0 0 24 24"
    >
      <path d="m12 3 1.4 4.2L18 9l-4.6 1.8L12 15l-1.4-4.2L6 9l4.6-1.8L12 3Zm7 10 .8 2.2L22 16l-2.2.8L19 19l-.8-2.2L16 16l2.2-.8L19 13ZM5 14l.9 2.6L8.5 18l-2.6 1.4L5 22l-.9-2.6L1.5 18l2.6-1.4L5 14Z" />
    </svg>
  );
}

function getAccuracyTone(value: number): "green" | "yellow" | "orange" | "red" {
  if (value >= 85) {
    return "green";
  }
  if (value >= 70) {
    return "yellow";
  }
  if (value >= 50) {
    return "orange";
  }
  return "red";
}

function AccuracyStat({ value }: { value: number }) {
  const tone = getAccuracyTone(value);
  const tooltipId = useId();
  const [isTooltipOpen, setIsTooltipOpen] = useState(false);
  const hintClassName = isTooltipOpen
    ? `${styles.accuracyHint} ${styles.accuracyHintOpen}`
    : styles.accuracyHint;

  return (
    <span className={hintClassName}>
      <span
        aria-describedby={tooltipId}
        aria-label="Точность колоды"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={value}
        aria-valuetext={`${value}%`}
        className={`${styles.accuracy} ${styles[`accuracy${tone}`]}`}
        onBlur={() => setIsTooltipOpen(false)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setIsTooltipOpen(false);
            event.currentTarget.blur();
          } else if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setIsTooltipOpen((isOpen) => !isOpen);
          }
        }}
        onPointerDown={(event) => {
          if (event.button === 0) {
            setIsTooltipOpen((isOpen) => !isOpen);
          }
        }}
        role="meter"
        tabIndex={0}
      >
        {value}
      </span>
      <span className={styles.accuracyTooltip} id={tooltipId} role="tooltip">
        <strong>Точность колоды</strong>
        <span>Правильных ответов — {value}%</span>
      </span>
    </span>
  );
}

interface DeckCardProps {
  canEdit: boolean;
  deck: LibraryDeckItem;
  favouriteError: unknown | null;
  isFavouriteUpdating: boolean;
  onFavouriteChange: (deckUuid: string, value: boolean) => void;
}

function DeckCard({
  canEdit,
  deck,
  favouriteError,
  isFavouriteUpdating,
  onFavouriteChange,
}: DeckCardProps) {
  const previewCards = deck.cards.slice(0, 2);
  const favouriteErrorId = `favourite-error-${deck.uuid}`;
  const favouriteAction = deck.isFavourite ? "Удалить из избранного" : "Добавить в избранное";

  return (
    <article className={styles.deckCard} data-deck-uuid={deck.uuid}>
      <div className={styles.deckTopline}>
        <AccuracyStat value={deck.accuracy} />
        <button
          aria-describedby={favouriteError === null ? undefined : favouriteErrorId}
          aria-label={`${favouriteAction}: «${deck.title}»`}
          aria-pressed={deck.isFavourite}
          className={deck.isFavourite ? styles.favouriteActive : styles.favourite}
          disabled={isFavouriteUpdating}
          onClick={() => onFavouriteChange(deck.uuid, !deck.isFavourite)}
          title={isFavouriteUpdating ? "Сохраняем…" : favouriteAction}
          type="button"
        >
          <Glyph name="heart" />
        </button>
      </div>
      {favouriteError === null ? null : (
        <p className={styles.favouriteError} id={favouriteErrorId} role="alert">
          {getFavouriteErrorMessage(favouriteError)}
        </p>
      )}

      <div className={styles.deckHero}>
        <div className={styles.deckCopy}>
          <h2 title={deck.title}>{deck.title}</h2>
          <p>{deck.description ?? "Без описания"}</p>
        </div>
      </div>

      <section aria-label={`Первые карточки колоды «${deck.title}»`} className={styles.deckPreview}>
        {previewCards.length > 0 ? (
          <ul className={styles.previewList}>
            {previewCards.map((card) => (
              <li data-card-uuid={card.uuid} key={card.uuid}>
                <span className={styles.previewAccent} />
                <span className={styles.previewFront} title={card.frontText}>
                  {card.frontText}
                </span>
                <span aria-hidden="true" className={styles.previewDivider}>
                  —
                </span>
                <span className={styles.previewBack} title={card.backText}>
                  {card.backText}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className={styles.emptyPreview} role="status">
            <strong>Карточек нет</strong>
            <span>Добавьте первую карточку в колоду</span>
          </div>
        )}
      </section>

      <div className={styles.deckActions}>
        {canEdit ? (
          <Link
            aria-label={`Редактировать колоду «${deck.title}»`}
            className={styles.editButton}
            title={`Редактировать колоду «${deck.title}»`}
            to={`/library/${deck.uuid}/edit`}
          >
            <Glyph name="pencil" />
            <span>Редактировать</span>
          </Link>
        ) : (
          <button
            aria-label={`Колоду «${deck.title}» может редактировать только владелец`}
            className={styles.editButton}
            disabled
            title="Редактировать эту колоду может только владелец"
            type="button"
          >
            <Glyph name="pencil" />
            <span>Редактировать</span>
          </button>
        )}
        <button
          aria-label={`Начать колоду «${deck.title}» — пока недоступно`}
          className={styles.startButton}
          disabled
          title="Практика колоды пока не подключена"
          type="button"
        >
          <Glyph name="play" />
          <span>Начать</span>
        </button>
      </div>

      <footer className={styles.deckMeta}>
        <span>
          <DashboardIcon name="book" />
          <span>Всего слов: {numberFormatter.format(deck.totalWordsCount)}</span>
        </span>
        <span className={styles.metaDivider} aria-hidden="true" />
        <span>
          <DashboardIcon name="clock" />
          <span>Последнее обновление: </span>
          <time dateTime={deck.updatedAt ?? undefined}>
            {formatUpdatedAt(deck.updatedAt ?? null)}
          </time>
        </span>
      </footer>
    </article>
  );
}

type CardActionGlyphName = "add" | "delete" | "edit" | "menu";

function CardActionGlyph({ name }: { name: CardActionGlyphName }) {
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

  if (name === "add") {
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
        <path d="M4.5 6.5h8.2a3 3 0 0 1 3 3v10H7.5a3 3 0 0 1-3-3v-10Z" />
        <path d="M7.5 3.5h8.2a3 3 0 0 1 3 3v7M12 10v6M9 13h6" />
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

interface CardActionsProps {
  card: LibraryCard;
  isDeleting: boolean;
  onAdd: () => void;
  onDelete: () => void;
  onEdit: () => void;
}

function CardActions({ card, isDeleting, onAdd, onDelete, onEdit }: CardActionsProps) {
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
    const estimatedMenuHeight = 142;
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

  function handleEdit(): void {
    menuRef.current?.hidePopover();
    onEdit();
  }

  function handleDelete(): void {
    menuRef.current?.hidePopover();
    onDelete();
  }

  function handleAdd(): void {
    menuRef.current?.hidePopover();
    onAdd();
  }

  return (
    <div className={styles.cardActions}>
      <button
        aria-label={`Действия с карточкой «${card.backText}»`}
        className={styles.cardActionsTrigger}
        id={triggerId}
        onClick={positionMenu}
        popoverTarget={menuId}
        popoverTargetAction="toggle"
        ref={triggerRef}
        title="Действия"
        type="button"
      >
        <CardActionGlyph name="menu" />
      </button>
      <div
        aria-labelledby={triggerId}
        className={styles.cardActionsMenu}
        id={menuId}
        popover="auto"
        ref={menuRef}
        role="group"
      >
        <button
          className={styles.cardEditAction}
          data-card-action="edit"
          disabled={isDeleting}
          onClick={handleEdit}
          type="button"
        >
          <CardActionGlyph name="edit" />
          <span>Редактировать</span>
        </button>
        <button
          aria-haspopup="dialog"
          className={styles.cardAddAction}
          data-card-action="add-to-deck"
          disabled={isDeleting}
          onClick={handleAdd}
          title="Добавить карточку в одну или несколько колод"
          type="button"
        >
          <CardActionGlyph name="add" />
          <span>Добавить в колоду</span>
        </button>
        <span aria-hidden="true" className={styles.cardActionsDivider} />
        <button
          className={styles.cardDeleteAction}
          data-card-action="delete"
          disabled={isDeleting}
          onClick={handleDelete}
          title="Удалить карточку"
          type="button"
        >
          <CardActionGlyph name="delete" />
          <span>{isDeleting ? "Удаляем…" : "Удалить"}</span>
        </button>
      </div>
    </div>
  );
}

interface LibraryCardRowProps {
  card: LibraryCard;
  onCardAssigned?: () => void;
  onDelete: (cardUuid: string) => Promise<void>;
  onUpdate: (cardUuid: string, input: UpdateLibraryCardInput) => Promise<void>;
}

function LibraryCardRow({ card, onCardAssigned, onDelete, onUpdate }: LibraryCardRowProps) {
  const isMountedRef = useRef(true);
  const deleteInFlightRef = useRef(false);
  const [isDeckPickerOpen, setIsDeckPickerOpen] = useState(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown | null>(null);
  const cardRowClassName = isDeleting
    ? `${styles.cardRow} ${styles.cardRowDeleting}`
    : styles.cardRow;

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  async function handleDelete(): Promise<void> {
    if (deleteInFlightRef.current) {
      return;
    }

    deleteInFlightRef.current = true;
    setDeleteError(null);
    setIsDeleting(true);

    try {
      await onDelete(card.uuid);
    } catch (error: unknown) {
      if (isMountedRef.current && (!isApiError(error) || error.code !== "REQUEST_ABORTED")) {
        setDeleteError(error);
      }
    } finally {
      deleteInFlightRef.current = false;
      if (isMountedRef.current) {
        setIsDeleting(false);
      }
    }
  }

  return (
    <li aria-busy={isDeleting} className={cardRowClassName} data-card-uuid={card.uuid}>
      <div className={`${styles.cardFace} ${styles.cardFaceSource}`}>
        <span className={styles.languageBadge}>{card.targetLang.toUpperCase()}</span>
        <div className={styles.cardFaceCopy}>
          <p className={styles.cardWord} title={card.backText}>
            <span className={styles.visuallyHidden}>Слово: </span>
            <span lang={card.targetLang}>{card.backText}</span>
          </p>
        </div>
      </div>

      <div className={`${styles.cardFace} ${styles.cardFaceTarget}`}>
        <span className={styles.languageBadge}>{card.sourceLang.toUpperCase()}</span>
        <div className={styles.cardFaceCopy}>
          <p className={styles.cardTranslation} title={card.frontText}>
            <span className={styles.visuallyHidden}>Перевод: </span>
            <span lang={card.sourceLang}>{card.frontText}</span>
          </p>
        </div>
      </div>

      <CardActions
        card={card}
        isDeleting={isDeleting}
        onAdd={() => setIsDeckPickerOpen(true)}
        onDelete={() => void handleDelete()}
        onEdit={() => setIsEditorOpen(true)}
      />
      {deleteError === null ? null : (
        <p className={styles.cardMutationError} role="alert">
          {getCardDeleteErrorMessage(deleteError)}
        </p>
      )}
      {isEditorOpen ? (
        <CardEditorDialog
          card={card}
          onClose={() => setIsEditorOpen(false)}
          onSave={(input) => onUpdate(card.uuid, input)}
        />
      ) : null}
      {isDeckPickerOpen ? (
        <AddCardToDeckDialog
          card={card}
          onAssigned={onCardAssigned}
          onClose={() => setIsDeckPickerOpen(false)}
        />
      ) : null}
    </li>
  );
}

interface LibraryTabsProps {
  activeView: LibraryView;
  onChange: (view: LibraryView) => void;
}

function LibraryTabs({ activeView, onChange }: LibraryTabsProps) {
  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    let nextView: LibraryView | null = null;

    if (event.key === "ArrowLeft" || event.key === "Home") {
      nextView = "decks";
    } else if (event.key === "ArrowRight" || event.key === "End") {
      nextView = "cards";
    }
    if (nextView === null) {
      return;
    }

    event.preventDefault();
    onChange(nextView);
    document.getElementById(`library-${nextView}-tab`)?.focus();
  }

  return (
    <div
      aria-label="Содержимое библиотеки"
      className={styles.librarySwitch}
      data-active={activeView}
      onKeyDown={handleKeyDown}
      role="tablist"
    >
      <span aria-hidden="true" className={styles.switchThumb} />
      <button
        aria-controls="library-decks-panel"
        aria-selected={activeView === "decks"}
        className={styles.switchTab}
        id="library-decks-tab"
        onClick={() => onChange("decks")}
        role="tab"
        tabIndex={activeView === "decks" ? 0 : -1}
        type="button"
      >
        Колоды
      </button>
      <button
        aria-controls="library-cards-panel"
        aria-selected={activeView === "cards"}
        className={styles.switchTab}
        id="library-cards-tab"
        onClick={() => onChange("cards")}
        role="tab"
        tabIndex={activeView === "cards" ? 0 : -1}
        type="button"
      >
        Карточки
      </button>
    </div>
  );
}

function DeckSkeletons() {
  return (
    <div aria-label="Загрузка колод" className={styles.decksGrid} role="status">
      {Array.from({ length: 8 }, (_, index) => (
        <div aria-hidden="true" className={styles.skeleton} key={index} />
      ))}
    </div>
  );
}

function CardSkeletons() {
  return (
    <div aria-label="Загрузка карточек" className={styles.cardSkeletons} role="status">
      {Array.from({ length: 5 }, (_, index) => (
        <div aria-hidden="true" className={styles.cardSkeleton} key={index} />
      ))}
    </div>
  );
}

interface StateMessageProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

function StateMessage({ title, description, actionLabel, onAction }: StateMessageProps) {
  return (
    <div className={styles.stateMessage} role={onAction ? "alert" : "status"}>
      <span aria-hidden="true" className={styles.stateMark}>
        Etch
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {actionLabel && onAction ? (
        <button onClick={onAction} type="button">
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

export function LibraryCardsPanel({
  cardLibrary,
  isHidden,
  onCardAssigned,
}: {
  cardLibrary: UseLibraryCardsResult;
  isHidden: boolean;
  onCardAssigned?: () => void;
}) {
  return (
    <section
      aria-labelledby="library-cards-tab"
      aria-busy={cardLibrary.status === "loading" || cardLibrary.isLoadingMore}
      className={styles.cardsPanel}
      hidden={isHidden}
      id="library-cards-panel"
      role="tabpanel"
      tabIndex={0}
    >
      {cardLibrary.status === "loading" ? <CardSkeletons /> : null}
      {cardLibrary.status === "error" ? (
        <StateMessage
          actionLabel="Попробовать снова"
          description={getLibraryCardsErrorMessage(cardLibrary.error)}
          onAction={cardLibrary.retry}
          title="Карточки не загрузились"
        />
      ) : null}
      {cardLibrary.status === "success" &&
      cardLibrary.cards.length === 0 &&
      !cardLibrary.hasMore ? (
        <StateMessage
          description="Когда у вас появятся карточки, они соберутся здесь."
          title="Карточек пока нет"
        />
      ) : null}
      {cardLibrary.status === "success" && (cardLibrary.cards.length > 0 || cardLibrary.hasMore) ? (
        <>
          <div aria-live="polite" className={styles.cardsSummary}>
            <Glyph name="sparkles" />
            <span>
              Загружено карточек: <strong>{cardLibrary.cards.length}</strong>
            </span>
          </div>
          <ul className={styles.cardsList}>
            {cardLibrary.cards.map((card) => (
              <LibraryCardRow
                card={card}
                key={card.uuid}
                onCardAssigned={onCardAssigned}
                onDelete={cardLibrary.deleteCard}
                onUpdate={cardLibrary.updateCard}
              />
            ))}
          </ul>
          {cardLibrary.loadMoreError ? (
            <p className={styles.loadMoreError} role="alert">
              {getLibraryCardsErrorMessage(cardLibrary.loadMoreError)}
            </p>
          ) : null}
          {cardLibrary.hasMore ? (
            <button
              className={styles.loadMoreButton}
              disabled={cardLibrary.isLoadingMore}
              onClick={cardLibrary.loadMore}
              type="button"
            >
              <span>{cardLibrary.isLoadingMore ? "Загружаем…" : "Показать ещё"}</span>
              <DashboardIcon name="chevron" />
            </button>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

export function LibraryCreateButton({
  activeView,
  onCreateCard,
  onCreateDeck,
}: {
  activeView: LibraryView;
  onCreateCard: () => void;
  onCreateDeck: () => void;
}) {
  const label = activeView === "decks" ? "Новая колода" : "Новая карточка";
  const isDeckView = activeView === "decks";

  return (
    <button
      className={styles.newDeckButton}
      onClick={isDeckView ? onCreateDeck : onCreateCard}
      title={isDeckView ? "Создать новую колоду" : "Создать новую карточку"}
      type="button"
    >
      <DashboardIcon name="plus" />
      <span>{label}</span>
    </button>
  );
}

export function LibraryPage() {
  const [activeView, setActiveView] = useState<LibraryView>("decks");
  const [hasOpenedCards, setHasOpenedCards] = useState(false);
  const [isCreateCardOpen, setIsCreateCardOpen] = useState(false);
  const [isCreateDeckOpen, setIsCreateDeckOpen] = useState(false);
  const { user } = useAuth();
  const library = useLibraryDecks();
  const cardLibrary = useLibraryCards({ enabled: hasOpenedCards });

  function handleViewChange(view: LibraryView): void {
    setActiveView(view);
    if (view === "cards") {
      setHasOpenedCards(true);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.library}>
        <header className={styles.libraryHeader}>
          <div>
            <span className={styles.eyebrow}>Ваше пространство</span>
            <h1>Библиотека</h1>
          </div>
          <LibraryCreateButton
            activeView={activeView}
            onCreateCard={() => setIsCreateCardOpen(true)}
            onCreateDeck={() => setIsCreateDeckOpen(true)}
          />
        </header>

        <div className={styles.toolbar}>
          <LibraryTabs activeView={activeView} onChange={handleViewChange} />
          {activeView === "decks" ? (
            <div className={styles.toolbarDetails}>
              <button
                aria-controls="library-decks-panel"
                aria-pressed={library.onlyFavourites}
                className={
                  library.onlyFavourites ? styles.favouritesFilterActive : styles.favouritesFilter
                }
                onClick={() => library.setOnlyFavourites(!library.onlyFavourites)}
                type="button"
              >
                <Glyph name="heart" />
                <span>Только любимые</span>
              </button>
              {library.status === "success" ? (
                <div aria-live="polite" className={styles.summary}>
                  <Glyph name="sparkles" />
                  <span>
                    <strong>{library.decks.length}</strong>{" "}
                    {library.onlyFavourites ? "любимых колод" : "колод"} загружено
                  </span>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <section
          aria-labelledby="library-decks-tab"
          aria-busy={library.status === "loading" || library.isLoadingMore}
          className={styles.libraryPanel}
          hidden={activeView !== "decks"}
          id="library-decks-panel"
          role="tabpanel"
        >
          {library.status === "loading" ? <DeckSkeletons /> : null}
          {library.status === "error" ? (
            <StateMessage
              actionLabel="Попробовать снова"
              description={getLibraryErrorMessage(library.error)}
              onAction={library.retry}
              title={
                library.onlyFavourites
                  ? "Любимые колоды не загрузились"
                  : "Библиотека не загрузилась"
              }
            />
          ) : null}
          {library.status === "success" && library.decks.length === 0 && !library.hasMore ? (
            <StateMessage
              description={
                library.onlyFavourites
                  ? "Добавьте колоды в любимые, и они появятся здесь."
                  : "Когда у вас появятся колоды, они соберутся здесь."
              }
              title={library.onlyFavourites ? "Любимых колод пока нет" : "В библиотеке пока пусто"}
            />
          ) : null}
          {library.status === "success" && (library.decks.length > 0 || library.hasMore) ? (
            <>
              <div className={styles.decksGrid}>
                {library.decks.map((deck) => (
                  <DeckCard
                    canEdit={!("ownerUuid" in deck) || deck.ownerUuid === user?.uuid}
                    deck={deck}
                    favouriteError={library.favouriteErrors[deck.uuid] ?? null}
                    isFavouriteUpdating={library.favouriteUpdatingDeckUuids.includes(deck.uuid)}
                    key={deck.uuid}
                    onFavouriteChange={library.setFavourite}
                  />
                ))}
              </div>
              {library.loadMoreError ? (
                <p className={styles.loadMoreError} role="alert">
                  {getLibraryErrorMessage(library.loadMoreError)}
                </p>
              ) : null}
              {library.hasMore ? (
                <button
                  className={styles.loadMoreButton}
                  disabled={library.isLoadingMore}
                  onClick={library.loadMore}
                  type="button"
                >
                  <span>{library.isLoadingMore ? "Загружаем…" : "Показать ещё"}</span>
                  <DashboardIcon name="chevron" />
                </button>
              ) : null}
            </>
          ) : null}
        </section>

        {hasOpenedCards ? (
          <LibraryCardsPanel
            cardLibrary={cardLibrary}
            isHidden={activeView !== "cards"}
            onCardAssigned={library.retry}
          />
        ) : (
          <section
            aria-labelledby="library-cards-tab"
            className={styles.cardsPanel}
            hidden
            id="library-cards-panel"
            role="tabpanel"
            tabIndex={0}
          />
        )}
        {isCreateCardOpen ? (
          <CardEditorDialog
            card={null}
            onClose={() => setIsCreateCardOpen(false)}
            onSave={cardLibrary.createCard}
          />
        ) : null}
        {isCreateDeckOpen ? (
          <DeckCreatorDialog
            onClose={() => setIsCreateDeckOpen(false)}
            onSave={library.createDeck}
          />
        ) : null}
      </section>
    </main>
  );
}

export default LibraryPage;
