import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { isApiError } from "../../api";
import { useAuth } from "../../auth/hooks/useAuth";
import { DashboardIcon } from "../../components/DashboardVisuals";
import { shouldOpenDeckCreator } from "../../features/library/model/library-navigation";
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
import {
  CARDS_LOADED_COUNT_FORMS,
  DECKS_LOADED_COUNT_FORMS,
  FAVOURITE_DECKS_LOADED_COUNT_FORMS,
  WORD_COUNT_FORMS,
  localizeCount,
  useLocale,
  type AppLocale,
} from "../../i18n";
import { AddCardToDeckDialog } from "./AddCardToDeckDialog";
import { CardEditorDialog } from "./CardEditorDialog";
import { DeckCreatorDialog } from "./DeckCreatorDialog";
import { DeckDeleteDialog } from "./DeckDeleteDialog";
import styles from "./LibraryPage.module.css";
import { OverflowingCardText } from "./OverflowingCardText";

type LibraryView = "decks" | "cards";

interface LibraryUiState {
  currentUserUuid: string | null;
  activeView: LibraryView;
  hasOpenedCards: boolean;
}

let cachedLibraryUiState: LibraryUiState | null = null;

const dateFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

function getDateFormatter(locale: AppLocale): Intl.DateTimeFormat {
  const cachedFormatter = dateFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  dateFormatters.set(locale, formatter);
  return formatter;
}

function formatUpdatedAt(value: string | null, locale: AppLocale): string | null {
  if (value === null) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : getDateFormatter(locale).format(date);
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
    if (error.status === 403 || error.status === 404) {
      return "Колода больше не найдена.";
    }
  }

  return "Не удалось изменить избранное. Попробуйте ещё раз.";
}

function getDeckDeleteErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось удалить колоду. Попробуйте ещё раз.";
  }
  if (error.status === 403 || error.status === 404) {
    return "Колода уже удалена или больше не существует.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может удалить колоду.";
  }

  return "Не удалось удалить колоду. Попробуйте ещё раз.";
}

function Glyph({ name }: { name: "delete" | "heart" | "pencil" | "play" | "sparkles" }) {
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
  if (name === "delete") {
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

function getAccuracyTone(
  value: number,
): "red" | "orange" | "yellow" | "green" | "turquoise" | "purple" {
  if (value >= 91) {
    return "purple";
  }
  if (value >= 81) {
    return "turquoise";
  }
  if (value >= 71) {
    return "green";
  }
  if (value >= 61) {
    return "yellow";
  }
  if (value >= 51) {
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
  deleteError: unknown | null;
  favouriteError: unknown | null;
  isDeleting: boolean;
  isFavouriteUpdating: boolean;
  onDelete: (deckUuid: string) => void;
  onFavouriteChange: (deckUuid: string, value: boolean) => void;
}

function DeckCard({
  canEdit,
  deck,
  deleteError,
  favouriteError,
  isDeleting,
  isFavouriteUpdating,
  onDelete,
  onFavouriteChange,
}: DeckCardProps) {
  const { locale } = useLocale();
  const previewCards = deck.cards.slice(0, 2);
  const hasMoreCards = deck.totalWordsCount > previewCards.length;
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const updatedAtLabel = formatUpdatedAt(deck.updatedAt ?? null, locale);
  const wordCount = localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale);
  const favouriteErrorId = `favourite-error-${deck.uuid}`;
  const deleteErrorId = `delete-error-${deck.uuid}`;
  const favouriteAction = deck.isFavourite ? "Удалить из избранного" : "Добавить в избранное";
  const canUseManagementActions = canEdit && !isDeleting;

  return (
    <article
      className={isDeleting ? `${styles.deckCard} ${styles.deckCardDeleting}` : styles.deckCard}
      data-deck-uuid={deck.uuid}
    >
      <div className={styles.deckTopline}>
        <AccuracyStat value={deck.accuracy} />
        <div className={styles.deckManagement}>
          <button
            aria-describedby={favouriteError === null ? undefined : favouriteErrorId}
            aria-label={`${favouriteAction}: «${deck.title}»`}
            aria-pressed={deck.isFavourite}
            className={deck.isFavourite ? styles.favouriteActive : styles.favourite}
            disabled={isFavouriteUpdating || isDeleting}
            onClick={() => onFavouriteChange(deck.uuid, !deck.isFavourite)}
            title={isFavouriteUpdating ? "Сохраняем…" : favouriteAction}
            type="button"
          >
            <Glyph name="heart" />
          </button>
          {canEdit ? (
            <>
              {canUseManagementActions ? (
                <Link
                  aria-label={`Редактировать колоду «${deck.title}»`}
                  className={styles.editButton}
                  title={`Редактировать колоду «${deck.title}»`}
                  to={`/library/${deck.uuid}/edit`}
                >
                  <Glyph name="pencil" />
                </Link>
              ) : (
                <button
                  aria-label={`Колода «${deck.title}» удаляется`}
                  className={styles.editButton}
                  disabled
                  title="Колода удаляется…"
                  type="button"
                >
                  <Glyph name="pencil" />
                </button>
              )}
              <button
                aria-describedby={deleteError === null ? undefined : deleteErrorId}
                aria-label={`Удалить колоду «${deck.title}»`}
                className={styles.deleteButton}
                disabled={!canUseManagementActions}
                onClick={() => setIsDeleteDialogOpen(true)}
                title={isDeleting ? "Удаляем…" : `Удалить колоду «${deck.title}»`}
                type="button"
              >
                <Glyph name="delete" />
              </button>
            </>
          ) : null}
        </div>
      </div>
      {favouriteError === null ? null : (
        <p className={styles.favouriteError} id={favouriteErrorId} role="alert">
          {getFavouriteErrorMessage(favouriteError)}
        </p>
      )}
      {deleteError === null ? null : (
        <p className={styles.deckDeleteError} id={deleteErrorId} role="alert">
          {getDeckDeleteErrorMessage(deleteError)}
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
                <OverflowingCardText
                  className={styles.previewFront}
                  label="Перевод"
                  language={card.frontLang}
                  text={card.frontText}
                />
                <span aria-hidden="true" className={styles.previewDivider}>
                  —
                </span>
                <OverflowingCardText
                  className={styles.previewBack}
                  label="Слово"
                  language={card.backLang}
                  text={card.backText}
                />
              </li>
            ))}
            {previewCards.length === 1 ? (
              <li
                aria-hidden="true"
                className={
                  hasMoreCards
                    ? styles.previewPlaceholder
                    : `${styles.previewPlaceholder} ${styles.previewPlaceholderEnd}`
                }
              >
                <span>{hasMoreCards ? "•••" : "Все карточки показаны"}</span>
              </li>
            ) : null}
          </ul>
        ) : (
          <div className={styles.emptyPreview} role="status">
            <strong>Карточек нет</strong>
            <span>Добавьте первую карточку в колоду</span>
          </div>
        )}
        <div
          aria-hidden="true"
          className={
            previewCards.length === 2
              ? `${styles.previewContinuation} ${styles.previewContinuationVisible} ${
                  hasMoreCards ? "" : styles.previewContinuationEnd
                }`
              : styles.previewContinuation
          }
        >
          <span>{hasMoreCards ? "•••" : "Все карточки показаны"}</span>
        </div>
      </section>

      <div className={styles.deckBottom}>
        <footer className={styles.deckMeta}>
          <p className={styles.deckWordCount}>{wordCount.text}</p>
          {deck.updatedAt !== null && updatedAtLabel !== null ? (
            <time
              className={styles.deckUpdatedAt}
              dateTime={deck.updatedAt}
              title={`Последнее обновление: ${updatedAtLabel}`}
            >
              <span className={styles.deckUpdatedLabel}>Обновлено</span>
              <span className={styles.deckUpdatedValue}>{updatedAtLabel}</span>
            </time>
          ) : null}
        </footer>
        {isDeleting ? (
          <button
            aria-label={`Колода «${deck.title}» удаляется`}
            className={styles.startButton}
            disabled
            title="Колода удаляется…"
            type="button"
          >
            <span>Удаляем…</span>
          </button>
        ) : (
          <Link
            aria-label={`Настроить тренировку по колоде «${deck.title}»`}
            className={styles.startButton}
            title={`Начать тренировку по колоде «${deck.title}»`}
            to={`/practice?deck=${encodeURIComponent(deck.uuid)}`}
          >
            <Glyph name="play" />
            <span>Начать</span>
          </Link>
        )}
      </div>
      {isDeleteDialogOpen ? (
        <DeckDeleteDialog
          deckTitle={deck.title}
          onClose={() => setIsDeleteDialogOpen(false)}
          onConfirm={() => onDelete(deck.uuid)}
        />
      ) : null}
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
        <span className={styles.languageBadge}>{card.backLang.toUpperCase()}</span>
        <div className={styles.cardFaceCopy}>
          <OverflowingCardText
            className={styles.cardWord}
            label="Слово"
            language={card.backLang}
            text={card.backText}
          />
        </div>
      </div>

      <div className={`${styles.cardFace} ${styles.cardFaceTarget}`}>
        <span className={styles.languageBadge}>{card.frontLang.toUpperCase()}</span>
        <div className={styles.cardFaceCopy}>
          <OverflowingCardText
            className={styles.cardTranslation}
            label="Перевод"
            language={card.frontLang}
            text={card.frontText}
          />
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
      {Array.from({ length: 3 }, (_, index) => (
        <div aria-hidden="true" className={styles.skeleton} key={index} />
      ))}
    </div>
  );
}

function DeckFilterLoading({ onlyFavourites }: { onlyFavourites: boolean }) {
  return (
    <div className={styles.deckFilterLoading} role="status">
      <span aria-hidden="true" className={styles.deckFilterSpinner} />
      <span>{onlyFavourites ? "Собираем любимые колоды…" : "Возвращаем все колоды…"}</span>
    </div>
  );
}

function CardSkeletons() {
  return (
    <div aria-label="Загрузка карточек" className={styles.cardSkeletons} role="status">
      {Array.from({ length: 3 }, (_, index) => (
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
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { locale } = useLocale();
  const currentUserUuid = user?.uuid ?? null;
  const openDeckCreatorFromNavigation = shouldOpenDeckCreator(location.state);
  const cachedUiStateAtMount =
    cachedLibraryUiState?.currentUserUuid === currentUserUuid ? cachedLibraryUiState : null;
  const [activeView, setActiveView] = useState<LibraryView>(
    cachedUiStateAtMount?.activeView ?? "decks",
  );
  const [hasOpenedCards, setHasOpenedCards] = useState(
    cachedUiStateAtMount?.hasOpenedCards ?? false,
  );
  const [isCreateCardOpen, setIsCreateCardOpen] = useState(false);
  const [isCreateDeckOpen, setIsCreateDeckOpen] = useState(openDeckCreatorFromNavigation);
  const [useCompactDeckLoading, setUseCompactDeckLoading] = useState(false);
  const [deckSearchQuery, setDeckSearchQuery] = useState("");
  const [cardAssignedNoticeKey, setCardAssignedNoticeKey] = useState<number | null>(null);
  const cardAssignedNoticeSequenceRef = useRef(0);
  const cardAssignedNoticeTimeoutRef = useRef<number | null>(null);
  const isDeckSearchActive = deckSearchQuery.trim().length > 0;
  const library = useLibraryDecks(currentUserUuid, deckSearchQuery);
  const cardLibrary = useLibraryCards({
    enabled: hasOpenedCards,
    onDeleteSuccess: library.retry,
  });
  const loadedDeckCount = localizeCount(
    library.decks.length,
    !isDeckSearchActive && library.onlyFavourites
      ? FAVOURITE_DECKS_LOADED_COUNT_FORMS
      : DECKS_LOADED_COUNT_FORMS,
    locale,
  );
  const loadedCardCount = localizeCount(cardLibrary.cards.length, CARDS_LOADED_COUNT_FORMS, locale);

  useEffect(() => {
    if (!openDeckCreatorFromNavigation) {
      return;
    }

    void navigate(
      {
        pathname: location.pathname,
        search: location.search,
        hash: location.hash,
      },
      { replace: true, state: null },
    );
  }, [location.hash, location.pathname, location.search, navigate, openDeckCreatorFromNavigation]);

  useEffect(
    () => () => {
      if (cardAssignedNoticeTimeoutRef.current !== null) {
        window.clearTimeout(cardAssignedNoticeTimeoutRef.current);
      }
    },
    [],
  );

  function handleViewChange(view: LibraryView): void {
    const nextHasOpenedCards = hasOpenedCards || view === "cards";
    cachedLibraryUiState = {
      currentUserUuid,
      activeView: view,
      hasOpenedCards: nextHasOpenedCards,
    };
    setActiveView(view);
    setHasOpenedCards(nextHasOpenedCards);
  }

  function handleCardAssigned(): void {
    library.retry();
    cardAssignedNoticeSequenceRef.current += 1;
    setCardAssignedNoticeKey(cardAssignedNoticeSequenceRef.current);

    if (cardAssignedNoticeTimeoutRef.current !== null) {
      window.clearTimeout(cardAssignedNoticeTimeoutRef.current);
    }
    cardAssignedNoticeTimeoutRef.current = window.setTimeout(() => {
      setCardAssignedNoticeKey(null);
      cardAssignedNoticeTimeoutRef.current = null;
    }, 3200);
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
              <label className={styles.deckSearchField}>
                <span className={styles.visuallyHidden}>Поиск по названию колоды</span>
                <input
                  autoComplete="off"
                  maxLength={150}
                  name="deck_search"
                  onChange={(event) => {
                    const nextQuery = event.currentTarget.value;
                    setDeckSearchQuery(nextQuery);
                    if (nextQuery.trim().length > 0 && library.onlyFavourites) {
                      library.setOnlyFavourites(false);
                    }
                  }}
                  placeholder="Поиск по колодам"
                  type="search"
                  value={deckSearchQuery}
                />
              </label>
              <button
                aria-controls="library-decks-panel"
                aria-pressed={library.onlyFavourites}
                className={
                  library.onlyFavourites ? styles.favouritesFilterActive : styles.favouritesFilter
                }
                disabled={library.status === "loading"}
                onClick={() => {
                  setDeckSearchQuery("");
                  setUseCompactDeckLoading(true);
                  library.setOnlyFavourites(!library.onlyFavourites);
                }}
                type="button"
              >
                <Glyph name="heart" />
                <span>Только любимые</span>
              </button>
              {library.status === "success" ? (
                <div aria-live="polite" className={styles.summary}>
                  <Glyph name="sparkles" />
                  <span>
                    <strong>{loadedDeckCount.formattedValue}</strong> {loadedDeckCount.unit}
                  </span>
                </div>
              ) : null}
            </div>
          ) : (
            <div className={`${styles.toolbarDetails} ${styles.cardsToolbarDetails}`}>
              {cardLibrary.status === "success" ? (
                <div aria-live="polite" className={styles.cardsSummary}>
                  <Glyph name="sparkles" />
                  <span>
                    <strong>{loadedCardCount.formattedValue}</strong> {loadedCardCount.unit}
                  </span>
                </div>
              ) : null}
            </div>
          )}
        </div>

        <section
          aria-labelledby="library-decks-tab"
          aria-busy={library.status === "loading" || library.isLoadingMore}
          className={styles.libraryPanel}
          hidden={activeView !== "decks"}
          id="library-decks-panel"
          role="tabpanel"
        >
          {library.status === "loading" ? (
            useCompactDeckLoading && !isDeckSearchActive ? (
              <DeckFilterLoading onlyFavourites={library.onlyFavourites} />
            ) : (
              <DeckSkeletons />
            )
          ) : null}
          {library.status === "error" ? (
            <StateMessage
              actionLabel="Попробовать снова"
              description={getLibraryErrorMessage(library.error)}
              onAction={library.retry}
              title={
                isDeckSearchActive
                  ? "Поиск недоступен"
                  : library.onlyFavourites
                    ? "Любимые колоды не загрузились"
                    : "Библиотека не загрузилась"
              }
            />
          ) : null}
          {isDeckSearchActive &&
          library.status === "success" &&
          library.decks.length === 0 &&
          !library.hasMore ? (
            <p className={styles.deckSearchEmpty} role="status">
              Колоды не найдены
            </p>
          ) : null}
          {!isDeckSearchActive &&
          library.status === "success" &&
          library.decks.length === 0 &&
          !library.hasMore ? (
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
                    canEdit={deck.ownerUuid === user?.uuid}
                    deck={deck}
                    deleteError={library.deleteErrors[deck.uuid] ?? null}
                    favouriteError={library.favouriteErrors[deck.uuid] ?? null}
                    isDeleting={library.deletingDeckUuids.includes(deck.uuid)}
                    isFavouriteUpdating={library.favouriteUpdatingDeckUuids.includes(deck.uuid)}
                    key={deck.uuid}
                    onDelete={library.deleteDeck}
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
            onCardAssigned={handleCardAssigned}
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
      {cardAssignedNoticeKey === null ? null : (
        <div
          aria-atomic="true"
          aria-live="polite"
          className={styles.cardAssignedToast}
          key={cardAssignedNoticeKey}
          role="status"
        >
          <span aria-hidden="true" className={styles.cardAssignedToastIcon}>
            ✓
          </span>
          <span>Карточка успешно добавлена</span>
        </div>
      )}
    </main>
  );
}

export default LibraryPage;
