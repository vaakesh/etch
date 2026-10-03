import {
  useEffect,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type PointerEvent,
} from "react";
import { isApiError } from "../../api";
import {
  checkDeckCapacity,
  parseCardImportJson,
  type CardImportIssue,
} from "../../features/library/model/card-import";
import { MAX_DECK_SIZE, isDeckSizeLimitError } from "../../features/library/model/deck-capacity";
import type {
  ImportLibraryCardsInput,
  ImportLibraryCardsResult,
  LibraryDeckItem,
} from "../../features/library/model/library-types";
import { useLongTextPreviewsEnabled } from "../../features/settings/model/useLongTextPreviewsEnabled";
import {
  CARD_COUNT_FORMS,
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
} from "../../i18n";
import styles from "./LibraryPage.module.css";

const EXAMPLE_JSON = `{
  "cards": [
    {
      "front_text": "привет",
      "back_text": "hello",
      "front_lang": "ru",
      "back_lang": "en"
    }
  ]
}`;

const MESSAGES = defineMessages(
  {
    title: "Импорт карточек",
    description: "Добавьте до 500 карточек из JSON.",
    close: "Закрыть окно импорта карточек",
    guideDescription:
      "Выберите колоду, вставьте JSON и нажмите «Импортировать». Новые карточки добавятся в конец колоды.",
    helpTitle: "Как это работает",
    formatTitle: "Формат JSON",
    formatDescription: "Поле cards обязательно. Языки можно не указывать — используются ru и en.",
    deckLabel: "Выберите колоду",
    emptyTitle: "Нет доступных колод",
    emptyDescription:
      "Сейчас на странице нет вашей колоды. Закройте окно, создайте или загрузите нужную колоду и повторите импорт.",
    cancel: "Отмена",
    continue: "Продолжить",
    chooseFile: "Открыть .json",
    fileLoaded: (name: string) => `Файл «${name}» загружен в поле`,
    jsonLabel: "Вставьте JSON",
    jsonHint: "От 1 до 500 карточек. front_text и back_text обязательны.",
    jsonPlaceholder: "Вставьте JSON сюда…",
    back: "Назад",
    importing: "Импортируем…",
    import: "Импортировать",
    success: (count: string) => `Успешно импортировано ${count}`,
    successDescription: (deckTitle: string) =>
      `Новые карточки добавлены в колоду «${deckTitle}» и уже готовы к тренировке.`,
    done: "Готово",
    errors: {
      empty: "Вставьте JSON или откройте файл перед импортом.",
      syntax: (position: number, character: string) =>
        `Неверный формат JSON: символ ${position}${character}. Проверьте запятые, кавычки и скобки.`,
      root: "Неверный формат JSON: в корне должен быть объект с полем cards.",
      cardsArray: "Неверный формат: поле cards должно быть массивом.",
      cardsEmpty: "Добавьте в массив cards хотя бы одну карточку.",
      cardsLimit: (limit: number) => `За один раз можно импортировать не больше ${limit} карточек.`,
      deckCapacity: (limit: number, freeSlots: number) =>
        freeSlots === 0
          ? `В колоде уже ${limit} карточек — это максимум, импортировать больше нельзя.`
          : `Столько карточек не поместится: лимит колоды — ${limit}, свободно ${freeSlots}.`,
      cardObject: (path: string) => `Неверный формат: ${path} должен быть объектом.`,
      text: (path: string, maxLength: number) =>
        `Проверьте ${path}: требуется непустой текст длиной до ${maxLength} символов.`,
      language: (path: string) =>
        `Проверьте ${path}: код языка должен содержать 2–3 латинские буквы.`,
      file: "Не удалось прочитать файл. Попробуйте выбрать его ещё раз или вставьте JSON вручную.",
      generic: "Не удалось импортировать карточки. Попробуйте ещё раз.",
      deckFull: (limit: number) =>
        `Карточки не поместились: в колоде не может быть больше ${limit} карточек.`,
      forbidden: "У вас нет доступа к импорту в эту колоду.",
      notFound: "Выбранная колода больше не существует.",
      validation: "Сервер отклонил формат карточек. Проверьте поля JSON.",
      invalid: "Сервер вернул неожиданный результат импорта.",
      aborted: "Импорт был отменён.",
      network: "Не удалось связаться с сервером. Проверьте подключение.",
      server: "Сервер временно не может импортировать карточки.",
    },
  },
  {
    title: "Import cards",
    description: "Add up to 500 cards from JSON.",
    close: "Close card import dialog",
    guideDescription:
      "Choose a deck, paste JSON, and select Import. New cards will be added to the end of the deck.",
    helpTitle: "How it works",
    formatTitle: "JSON format",
    formatDescription:
      "The cards field is required. Languages are optional and default to ru and en.",
    deckLabel: "Choose a deck",
    emptyTitle: "No decks available",
    emptyDescription:
      "None of your decks are currently on this page. Close this dialog, create or load the deck you need, then try again.",
    cancel: "Cancel",
    continue: "Continue",
    chooseFile: "Open .json",
    fileLoaded: (name: string) => `“${name}” loaded into the field`,
    jsonLabel: "Paste JSON",
    jsonHint: "Between 1 and 500 cards. front_text and back_text are required.",
    jsonPlaceholder: "Paste JSON here…",
    back: "Back",
    importing: "Importing…",
    import: "Import",
    success: (count: string) => `Successfully imported ${count}`,
    successDescription: (deckTitle: string) =>
      `The new cards were added to “${deckTitle}” and are ready to practice.`,
    done: "Done",
    errors: {
      empty: "Paste JSON or open a file before importing.",
      syntax: (position: number, character: string) =>
        `Invalid JSON at character ${position}${character}. Check the commas, quotes, and brackets.`,
      root: "Invalid JSON shape: the root must be an object with a cards field.",
      cardsArray: "Invalid format: cards must be an array.",
      cardsEmpty: "Add at least one card to the cards array.",
      cardsLimit: (limit: number) => `You can import no more than ${limit} cards at once.`,
      deckCapacity: (limit: number, freeSlots: number) =>
        freeSlots === 0
          ? `The deck already holds ${limit} cards — that's the maximum, so nothing more can be imported.`
          : `That many cards won't fit: the deck limit is ${limit} and only ${freeSlots} slots are left.`,
      cardObject: (path: string) => `Invalid format: ${path} must be an object.`,
      text: (path: string, maxLength: number) =>
        `Check ${path}: enter non-empty text no longer than ${maxLength} characters.`,
      language: (path: string) => `Check ${path}: language codes must contain 2–3 Latin letters.`,
      file: "We couldn't read that file. Choose it again or paste the JSON manually.",
      generic: "We couldn't import the cards. Try again.",
      deckFull: (limit: number) => `The cards didn't fit: a deck can hold at most ${limit} cards.`,
      forbidden: "You do not have permission to import into this deck.",
      notFound: "The selected deck no longer exists.",
      validation: "The server rejected the card format. Check the JSON fields.",
      invalid: "The server returned an unexpected import result.",
      aborted: "The import was canceled.",
      network: "We couldn't reach the server. Check your connection.",
      server: "The server cannot import cards right now.",
    },
  },
);

type ImportStep = "deck" | "json" | "success";

interface CardImportDialogProps {
  decks: readonly LibraryDeckItem[];
  onClose: () => void;
  onImport: (deckUuid: string, input: ImportLibraryCardsInput) => Promise<ImportLibraryCardsResult>;
}

function ImportGlyph({ name }: { name: "check" | "close" | "file" | "import" }) {
  if (name === "close") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="m7 7 10 10M17 7 7 17" />
      </svg>
    );
  }

  if (name === "check") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="m5 12.5 4.2 4.2L19.5 6.5" />
      </svg>
    );
  }

  if (name === "file") {
    return (
      <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="M6 3.5h8l4 4V21H6V3.5Z" />
        <path d="M14 3.5v4h4M9 13h6M9 16.5h4" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path d="M12 3v12M7.5 10.5 12 15l4.5-4.5" />
      <path d="M5 16.5V21h14v-4.5" />
    </svg>
  );
}

function getCharacterLabel(character: string | null): string {
  if (character === null) {
    return " (EOF)";
  }

  return ` = ${JSON.stringify(character)}`;
}

function getIssueMessage(issue: CardImportIssue, messages: (typeof MESSAGES)["ru-RU"]): string {
  switch (issue.code) {
    case "empty":
      return messages.errors.empty;
    case "json-syntax":
      return messages.errors.syntax(issue.position, getCharacterLabel(issue.character));
    case "root":
      return messages.errors.root;
    case "cards-array":
      return messages.errors.cardsArray;
    case "cards-empty":
      return messages.errors.cardsEmpty;
    case "cards-limit":
      return messages.errors.cardsLimit(issue.limit);
    case "deck-capacity":
      return messages.errors.deckCapacity(issue.limit, issue.freeSlots);
    case "card-object":
      return messages.errors.cardObject(issue.path);
    case "text":
      return messages.errors.text(issue.path, issue.maxLength);
    case "language":
      return messages.errors.language(issue.path);
  }
}

function getImportErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (isDeckSizeLimitError(error)) {
    return messages.errors.deckFull(MAX_DECK_SIZE);
  }
  if (!isApiError(error)) {
    return messages.errors.generic;
  }
  if (error.status === 403) {
    return messages.errors.forbidden;
  }
  if (error.status === 404) {
    return messages.errors.notFound;
  }
  if (error.status === 422) {
    return messages.errors.validation;
  }
  if (error.code === "INVALID_LIBRARY_RESPONSE") {
    return messages.errors.invalid;
  }
  if (error.code === "REQUEST_ABORTED") {
    return messages.errors.aborted;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.server;
  }

  return messages.errors.generic;
}

export function CardImportDialog({ decks, onClose, onImport }: CardImportDialogProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const longTextPreviewsEnabled = useLongTextPreviewsEnabled();
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isMountedRef = useRef(true);
  const isImportingRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();
  const deckLegendId = useId();
  const jsonInputId = useId();
  const jsonHintId = useId();
  const errorId = useId();
  const fileStatusId = useId();
  const [step, setStep] = useState<ImportStep>("deck");
  const [selectedDeckUuid, setSelectedDeckUuid] = useState("");
  const [jsonText, setJsonText] = useState("");
  const [loadedFileName, setLoadedFileName] = useState<string | null>(null);
  const [issue, setIssue] = useState<CardImportIssue | null>(null);
  const [importError, setImportError] = useState<unknown | null>(null);
  const [fileReadFailed, setFileReadFailed] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importedCount, setImportedCount] = useState<number | null>(null);
  const selectedDeck = decks.find((deck) => deck.uuid === selectedDeckUuid) ?? null;
  const errorMessage =
    issue !== null
      ? getIssueMessage(issue, messages)
      : fileReadFailed
        ? messages.errors.file
        : importError !== null
          ? getImportErrorMessage(importError, messages)
          : null;

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
    if (!isImportingRef.current) {
      dialogRef.current?.close();
    }
  }

  function handleBackdropPointerDown(event: PointerEvent<HTMLDialogElement>): void {
    if (event.target === event.currentTarget) {
      closeDialog();
    }
  }

  function clearErrors(): void {
    setIssue(null);
    setImportError(null);
    setFileReadFailed(false);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (file === undefined) {
      return;
    }

    clearErrors();
    try {
      const content = await file.text();
      if (isMountedRef.current) {
        setJsonText(content);
        setLoadedFileName(file.name);
        textareaRef.current?.focus();
      }
    } catch {
      if (isMountedRef.current) {
        setFileReadFailed(true);
      }
    } finally {
      input.value = "";
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    if (step === "deck") {
      if (selectedDeck === null) {
        return;
      }
      clearErrors();
      setStep("json");
      return;
    }

    if (step !== "json" || selectedDeck === null || isImportingRef.current) {
      return;
    }

    clearErrors();
    const parseResult = parseCardImportJson(jsonText);
    if (!parseResult.ok) {
      setIssue(parseResult.issue);
      textareaRef.current?.focus();
      return;
    }

    const capacityIssue = checkDeckCapacity(
      selectedDeck.totalWordsCount,
      parseResult.value.cards.length,
    );
    if (capacityIssue !== null) {
      setIssue(capacityIssue);
      textareaRef.current?.focus();
      return;
    }

    isImportingRef.current = true;
    setIsImporting(true);
    try {
      const result = await onImport(selectedDeck.uuid, parseResult.value);
      if (isMountedRef.current) {
        setImportedCount(result.importedCount);
        setStep("success");
      }
    } catch (error: unknown) {
      if (isMountedRef.current) {
        setImportError(error);
        textareaRef.current?.focus();
      }
    } finally {
      isImportingRef.current = false;
      if (isMountedRef.current) {
        setIsImporting(false);
      }
    }
  }

  return (
    <dialog
      aria-busy={isImporting}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      aria-modal="true"
      className={`${styles.cardEditorDialog} ${styles.cardImportDialog}`}
      data-card-import="true"
      onCancel={(event) => {
        if (isImportingRef.current) {
          event.preventDefault();
        }
      }}
      onClose={onClose}
      onPointerDown={handleBackdropPointerDown}
      ref={dialogRef}
    >
      <div className={styles.cardEditorShell}>
        <header className={styles.cardEditorHeader}>
          <div className={styles.cardEditorHeading}>
            <span aria-hidden="true" className={styles.cardEditorMark}>
              <ImportGlyph name="import" />
            </span>
            <div>
              <h2 id={titleId}>{messages.title}</h2>
              <p id={descriptionId}>{messages.description}</p>
            </div>
          </div>
          <button
            aria-label={messages.close}
            className={styles.cardEditorClose}
            disabled={isImporting}
            onClick={closeDialog}
            type="button"
          >
            <ImportGlyph name="close" />
          </button>
        </header>

        <form
          className={`${styles.cardEditorForm} ${styles.cardImportForm}`}
          onSubmit={handleSubmit}
        >
          {step === "deck" ? (
            <div className={styles.cardImportStep}>
              <section className={styles.cardImportHelp}>
                <div>
                  <strong>{messages.helpTitle}</strong>
                  <p>{messages.guideDescription}</p>
                </div>
                <div className={styles.cardImportExample}>
                  <strong>{messages.formatTitle}</strong>
                  <p>{messages.formatDescription}</p>
                  <pre aria-label={messages.formatTitle}>
                    <code>{EXAMPLE_JSON}</code>
                  </pre>
                </div>
              </section>

              {decks.length === 0 ? (
                <div className={styles.cardImportEmpty} role="status">
                  <strong>{messages.emptyTitle}</strong>
                  <p>{messages.emptyDescription}</p>
                </div>
              ) : (
                <fieldset
                  aria-labelledby={deckLegendId}
                  className={`${styles.cardDeckOptions} ${styles.cardImportDeckOptions}`}
                >
                  <legend id={deckLegendId}>{messages.deckLabel}</legend>
                  {decks.map((deck, index) => (
                    <label className={styles.cardDeckOption} key={deck.uuid}>
                      <input
                        autoFocus={index === 0}
                        checked={selectedDeckUuid === deck.uuid}
                        name="deck_uuid"
                        onChange={() => setSelectedDeckUuid(deck.uuid)}
                        type="radio"
                        value={deck.uuid}
                      />
                      <span aria-hidden="true" className={styles.cardDeckCheck}>
                        <ImportGlyph name="check" />
                      </span>
                      <strong
                        className={styles.cardDeckTitle}
                        title={longTextPreviewsEnabled ? deck.title : undefined}
                      >
                        {deck.title}
                      </strong>
                      <span className={styles.cardDeckMeta}>
                        <span className={styles.cardDeckCount}>
                          {localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale).text}
                        </span>
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}
            </div>
          ) : null}

          {step === "json" && selectedDeck !== null ? (
            <div className={styles.cardImportStep}>
              <div
                className={styles.cardImportSelectedDeck}
                title={longTextPreviewsEnabled ? selectedDeck.title : undefined}
              >
                <ImportGlyph name="check" />
                <strong>{selectedDeck.title}</strong>
              </div>

              <div className={styles.cardImportFieldHeader}>
                <label htmlFor={jsonInputId}>{messages.jsonLabel}</label>
                <label className={styles.cardImportFileButton}>
                  <ImportGlyph name="file" />
                  <span>{messages.chooseFile}</span>
                  <input accept=".json,application/json" onChange={handleFileChange} type="file" />
                </label>
              </div>
              <textarea
                aria-describedby={`${jsonHintId}${errorMessage === null ? "" : ` ${errorId}`}`}
                aria-invalid={errorMessage === null ? undefined : true}
                autoCapitalize="off"
                autoComplete="off"
                autoCorrect="off"
                autoFocus
                className={styles.cardImportTextarea}
                id={jsonInputId}
                name="cards_json"
                onChange={(event) => {
                  setJsonText(event.currentTarget.value);
                  setLoadedFileName(null);
                  clearErrors();
                }}
                placeholder={messages.jsonPlaceholder}
                ref={textareaRef}
                rows={14}
                spellCheck={false}
                value={jsonText}
              />
              <div className={styles.cardImportFieldMeta}>
                <small id={jsonHintId}>{messages.jsonHint}</small>
                <small>{jsonText.length.toLocaleString(locale)}</small>
              </div>
              {loadedFileName === null ? null : (
                <p className={styles.cardImportFileStatus} id={fileStatusId} role="status">
                  <ImportGlyph name="check" />
                  <span>{messages.fileLoaded(loadedFileName)}</span>
                </p>
              )}
              {errorMessage === null ? null : (
                <p className={styles.cardEditorError} id={errorId} role="alert">
                  {errorMessage}
                </p>
              )}
            </div>
          ) : null}

          {step === "success" && selectedDeck !== null && importedCount !== null ? (
            <div className={styles.cardImportSuccess} role="status">
              <span aria-hidden="true" className={styles.cardImportSuccessMark}>
                <ImportGlyph name="check" />
              </span>
              <strong>
                {messages.success(localizeCount(importedCount, CARD_COUNT_FORMS, locale).text)}
              </strong>
              <p>{messages.successDescription(selectedDeck.title)}</p>
            </div>
          ) : null}

          <footer className={`${styles.cardEditorFooter} ${styles.cardImportFooter}`}>
            <div className={styles.cardEditorButtons}>
              {step === "deck" ? (
                <>
                  <button className={styles.cardEditorCancel} onClick={closeDialog} type="button">
                    {messages.cancel}
                  </button>
                  <button
                    className={styles.cardEditorSave}
                    disabled={selectedDeck === null}
                    type="submit"
                  >
                    <span>{messages.continue}</span>
                    <span aria-hidden="true">→</span>
                  </button>
                </>
              ) : null}
              {step === "json" ? (
                <>
                  <button
                    className={styles.cardEditorCancel}
                    disabled={isImporting}
                    onClick={() => {
                      clearErrors();
                      setStep("deck");
                    }}
                    type="button"
                  >
                    {messages.back}
                  </button>
                  <button
                    className={styles.cardEditorSave}
                    disabled={isImporting || jsonText.trim().length === 0}
                    type="submit"
                  >
                    {isImporting ? (
                      <span aria-hidden="true" className={styles.cardEditorSpinner} />
                    ) : (
                      <ImportGlyph name="import" />
                    )}
                    <span>{isImporting ? messages.importing : messages.import}</span>
                  </button>
                </>
              ) : null}
              {step === "success" ? (
                <button className={styles.cardEditorSave} onClick={closeDialog} type="button">
                  <ImportGlyph name="check" />
                  <span>{messages.done}</span>
                </button>
              ) : null}
            </div>
          </footer>
        </form>
      </div>
    </dialog>
  );
}
