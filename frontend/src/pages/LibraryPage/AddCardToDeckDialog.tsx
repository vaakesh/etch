import { useEffect, useId, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { isApiError } from "../../api";
import type {
  LibraryCardDeckAddStatus,
  LibraryCard,
} from "../../features/library/model/library-types";
import { useCardDeckAssignment } from "../../features/library/model/useCardDeckAssignment";
import {
  DECKS_LEFT_TO_SAVE_COUNT_FORMS,
  SELECTED_DECK_COUNT_FORMS,
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
} from "../../i18n";
import styles from "./LibraryPage.module.css";

const MESSAGES = defineMessages(
  {
    errors: {
      loadGeneric: "Не удалось загрузить ваши колоды. Попробуйте ещё раз.",
      loadForbidden: "У вас нет доступа к списку колод.",
      loadInvalid: "Сервер вернул список колод в неожиданном формате.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      loadServer: "Сервер временно не может загрузить колоды.",
      saveGeneric: "Не удалось добавить карточку в выбранную колоду. Попробуйте ещё раз.",
      saveForbidden: "Нет доступа к карточке или одной из выбранных колод.",
      saveNotFound: "Карточка или одна из выбранных колод больше не найдена.",
      saveValidation: "Сервер не принял выбранную карточку или колоду.",
      saveAborted: "Добавление карточки было отменено.",
      saveServer: "Сервер временно не может добавить карточку в колоду.",
      partial: "Остальные изменения уже сохранены.",
    },
    eyebrow: "Быстрое добавление",
    title: "Добавить в колоду",
    description: "Выберите одну или несколько колод для карточки",
    close: "Закрыть окно выбора колод",
    loading: "Загрузка ваших колод",
    loadErrorTitle: "Колоды не загрузились",
    retry: "Попробовать снова",
    emptyTitle: "У вас пока нет колод",
    emptyDescription: "Создайте колоду во вкладке «Колоды», затем вернитесь к карточке.",
    optionsLegend: "Колоды для добавления карточки",
    retryShort: "повторить",
    added: "Карточка добавлена",
    alreadyAdded: "Карточка уже была в этой колоде",
    multiDeckHint: "Можно добавить карточку сразу в несколько колод.",
    cancel: "Отмена",
    saving: "Сохраняем…",
    save: "Сохранить",
  },
  {
    errors: {
      loadGeneric: "We couldn't load your decks. Try again.",
      loadForbidden: "You do not have access to the deck list.",
      loadInvalid: "The server returned an unexpected deck list.",
      network: "We couldn't reach the server. Check your connection.",
      loadServer: "The server cannot load your decks right now.",
      saveGeneric: "We couldn't add the card to the selected deck. Try again.",
      saveForbidden: "You do not have access to the card or one of the selected decks.",
      saveNotFound: "The card or one of the selected decks could not be found.",
      saveValidation: "The server rejected the selected card or deck.",
      saveAborted: "Adding the card was canceled.",
      saveServer: "The server cannot add the card to a deck right now.",
      partial: "Your other changes have already been saved.",
    },
    eyebrow: "Quick add",
    title: "Add to deck",
    description: "Choose one or more decks for",
    close: "Close deck picker",
    loading: "Loading your decks",
    loadErrorTitle: "Your decks didn't load",
    retry: "Try again",
    emptyTitle: "You don't have any decks yet",
    emptyDescription: "Create a deck on the Decks tab, then return to this card.",
    optionsLegend: "Decks for this card",
    retryShort: "retry",
    added: "Card added",
    alreadyAdded: "This card was already in the deck",
    multiDeckHint: "You can add a card to several decks at once.",
    cancel: "Cancel",
    saving: "Saving…",
    save: "Save",
  },
);

interface AddCardToDeckDialogProps {
  card: LibraryCard;
  onAssigned?: () => void;
  onClose: () => void;
}

function getDeckLoadErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.loadGeneric;
  }
  if (error.status === 403) {
    return messages.errors.loadForbidden;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.errors.loadInvalid;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.loadServer;
  }

  return messages.errors.loadGeneric;
}

function getDeckSaveErrorMessage(
  error: unknown,
  hasCompletedDecks: boolean,
  messages: (typeof MESSAGES)["ru-RU"],
): string {
  let message = messages.errors.saveGeneric;

  if (isApiError(error)) {
    if (error.status === 403) {
      message = messages.errors.saveForbidden;
    } else if (error.status === 404) {
      message = messages.errors.saveNotFound;
    } else if (error.status === 422) {
      message = messages.errors.saveValidation;
    } else if (error.code === "REQUEST_ABORTED") {
      message = messages.errors.saveAborted;
    } else if (error.status === 0) {
      message = messages.errors.network;
    } else if (error.status >= 500) {
      message = messages.errors.saveServer;
    }
  }

  return hasCompletedDecks ? `${message} ${messages.errors.partial}` : message;
}

function DeckAssignmentGlyph({ name }: { name: "check" | "close" | "deck" | "save" }) {
  if (name === "close") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="m7 7 10 10M17 7 7 17" />
      </svg>
    );
  }

  if (name === "check") {
    return (
      <svg
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.2"
        viewBox="0 0 24 24"
      >
        <path d="m6.5 12.5 3.4 3.4 7.8-8" />
      </svg>
    );
  }

  if (name === "deck") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="M5 6.5h10.5A3.5 3.5 0 0 1 19 10v9H8.5A3.5 3.5 0 0 1 5 15.5v-9Z" />
        <path d="M8 3.5h8.5A2.5 2.5 0 0 1 19 6v8M12 10v6M9 13h6" />
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

export function AddCardToDeckDialog({ card, onAssigned, onClose }: AddCardToDeckDialogProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const assignment = useCardDeckAssignment(card.uuid);
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const isMountedRef = useRef(true);
  const isSavingRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();
  const optionsLegendId = useId();
  const [selectedDeckUuids, setSelectedDeckUuids] = useState<readonly string[]>([]);
  const [completedDecks, setCompletedDecks] = useState<
    Readonly<Record<string, LibraryCardDeckAddStatus>>
  >({});
  const [saveFailures, setSaveFailures] = useState<Readonly<Record<string, unknown>>>({});
  const [isSaving, setIsSaving] = useState(false);
  const pendingCount = selectedDeckUuids.filter(
    (deckUuid) => completedDecks[deckUuid] === undefined,
  ).length;
  const completedCount = Object.keys(completedDecks).length;
  const selectedDeckCount = localizeCount(pendingCount, SELECTED_DECK_COUNT_FORMS, locale);
  const decksLeftToSaveCount = localizeCount(pendingCount, DECKS_LEFT_TO_SAVE_COUNT_FORMS, locale);
  const firstSaveFailure = Object.values(saveFailures)[0] ?? null;
  const canSave = assignment.status === "success" && pendingCount > 0;

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

  function toggleDeck(deckUuid: string): void {
    if (completedDecks[deckUuid] !== undefined) {
      return;
    }

    setSelectedDeckUuids((currentDeckUuids) =>
      currentDeckUuids.includes(deckUuid)
        ? currentDeckUuids.filter((currentDeckUuid) => currentDeckUuid !== deckUuid)
        : [...currentDeckUuids, deckUuid],
    );
    setSaveFailures((currentFailures) => {
      if (!(deckUuid in currentFailures)) {
        return currentFailures;
      }

      const nextFailures = { ...currentFailures };
      delete nextFailures[deckUuid];
      return nextFailures;
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isSavingRef.current || !canSave) {
      return;
    }

    const pendingDeckUuids = selectedDeckUuids.filter(
      (deckUuid) => completedDecks[deckUuid] === undefined,
    );
    isSavingRef.current = true;
    setSaveFailures({});
    setIsSaving(true);

    try {
      const outcomes = await assignment.assignToDecks(pendingDeckUuids);

      if (!isMountedRef.current) {
        return;
      }

      const nextCompletedDecks: Record<string, LibraryCardDeckAddStatus> = {
        ...completedDecks,
      };
      const nextFailures: Record<string, unknown> = {};

      outcomes.forEach((outcome) => {
        if (outcome.status === "failed") {
          nextFailures[outcome.deckUuid] = outcome.error;
        } else {
          nextCompletedDecks[outcome.deckUuid] = outcome.status;
        }
      });

      if (outcomes.some((outcome) => outcome.status === "added")) {
        onAssigned?.();
      }

      setCompletedDecks(nextCompletedDecks);
      setSaveFailures(nextFailures);
      setSelectedDeckUuids(Object.keys(nextFailures));

      if (Object.keys(nextFailures).length === 0) {
        dialogRef.current?.close();
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
      className={`${styles.cardEditorDialog} ${styles.cardDeckDialog}`}
      data-card-deck-picker={card.uuid}
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
              <DeckAssignmentGlyph name="deck" />
            </span>
            <div>
              <span className={styles.cardEditorEyebrow}>{messages.eyebrow}</span>
              <h2 id={titleId}>{messages.title}</h2>
              <p id={descriptionId}>
                {messages.description}
                <strong className={styles.cardDeckCardName} title={card.backText}>
                  {` «${card.backText}»`}
                </strong>
                .
              </p>
            </div>
          </div>
          <button
            aria-label={messages.close}
            className={styles.cardEditorClose}
            disabled={isSaving}
            onClick={closeDialog}
            type="button"
          >
            <DeckAssignmentGlyph name="close" />
          </button>
        </header>

        <form className={styles.cardEditorForm} onSubmit={handleSubmit}>
          <div className={styles.cardDeckPicker}>
            {assignment.status === "loading" ? (
              <div aria-label={messages.loading} className={styles.cardDeckSkeletons} role="status">
                {Array.from({ length: 4 }, (_, index) => (
                  <span aria-hidden="true" key={index} />
                ))}
              </div>
            ) : null}

            {assignment.status === "error" ? (
              <div className={styles.cardDeckState} role="alert">
                <strong>{messages.loadErrorTitle}</strong>
                <p>{getDeckLoadErrorMessage(assignment.error, messages)}</p>
                <button disabled={isSaving} onClick={assignment.retry} type="button">
                  {messages.retry}
                </button>
              </div>
            ) : null}

            {assignment.status === "success" && assignment.decks.length === 0 ? (
              <div className={styles.cardDeckState} role="status">
                <strong>{messages.emptyTitle}</strong>
                <p>{messages.emptyDescription}</p>
              </div>
            ) : null}

            {assignment.status === "success" && assignment.decks.length > 0 ? (
              <fieldset aria-labelledby={optionsLegendId} className={styles.cardDeckOptions}>
                <legend className={styles.visuallyHidden} id={optionsLegendId}>
                  {messages.optionsLegend}
                </legend>
                {assignment.decks.map((deck, index) => {
                  const completedStatus = completedDecks[deck.uuid];
                  const hasFailed = saveFailures[deck.uuid] !== undefined;
                  const isChecked =
                    completedStatus !== undefined || selectedDeckUuids.includes(deck.uuid);
                  const assignmentState =
                    completedStatus !== undefined ? "completed" : hasFailed ? "failed" : undefined;

                  return (
                    <label
                      className={styles.cardDeckOption}
                      data-assignment-state={assignmentState}
                      key={deck.uuid}
                    >
                      <input
                        autoFocus={index === 0}
                        checked={isChecked}
                        disabled={isSaving || completedStatus !== undefined}
                        name="deck_uuid"
                        onChange={() => toggleDeck(deck.uuid)}
                        type="checkbox"
                        value={deck.uuid}
                      />
                      <span aria-hidden="true" className={styles.cardDeckCheck}>
                        <DeckAssignmentGlyph name="check" />
                      </span>
                      <strong className={styles.cardDeckTitle} title={deck.title}>
                        {deck.title}
                      </strong>
                      <span className={styles.cardDeckMeta}>
                        <span className={styles.cardDeckCount}>
                          {localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale).text}
                        </span>
                        {hasFailed ? (
                          <small className={styles.cardDeckRetryLabel}>{messages.retryShort}</small>
                        ) : null}
                      </span>
                      {completedStatus === undefined ? null : (
                        <span className={styles.visuallyHidden}>
                          {completedStatus === "added" ? messages.added : messages.alreadyAdded}
                        </span>
                      )}
                    </label>
                  );
                })}
              </fieldset>
            ) : null}
          </div>

          {firstSaveFailure === null ? null : (
            <p className={styles.cardEditorError} role="alert">
              {getDeckSaveErrorMessage(firstSaveFailure, completedCount > 0, messages)}
            </p>
          )}

          <footer className={styles.cardEditorFooter}>
            <p aria-live="polite">
              {assignment.status === "success" && assignment.decks.length > 0
                ? completedCount > 0
                  ? decksLeftToSaveCount.text
                  : selectedDeckCount.text
                : messages.multiDeckHint}
            </p>
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
                  <DeckAssignmentGlyph name="save" />
                )}
                <span>{isSaving ? messages.saving : messages.save}</span>
              </button>
            </div>
          </footer>
        </form>
      </div>
    </dialog>
  );
}
