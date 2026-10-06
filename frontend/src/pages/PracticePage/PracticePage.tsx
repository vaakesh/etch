import { useEffect, useId, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { API_ERROR_CODES, hasAnyApiErrorCode, hasApiErrorCode, isApiError } from "../../api";
import { DashboardIcon } from "../../components/DashboardVisuals";
import { getPracticePaginationTokens } from "../../features/practice/model/practice-pagination";
import { usePracticeDeckAvailability } from "../../features/practice/model/usePracticeDeckAvailability";
import {
  usePracticeActivity,
  type UsePracticeActivityResult,
} from "../../features/practice/model/usePracticeActivity";
import type {
  CardSide,
  PracticeCard,
  PracticeHistoryFilter,
  PracticeHistorySession,
  PracticeSession,
} from "../../features/practice/model/practice-types";
import { usePracticeHistory } from "../../features/practice/model/usePracticeHistory";
import {
  MAX_SESSION_SIZE,
  canPracticeEntireDeck,
  clampCustomSessionSize,
  getWordsPerSession,
  readCustomSessionSize,
  type PracticeSessionScope,
} from "../../features/practice/model/practice-session-size";
import {
  usePracticeSession,
  type PracticeCardFeedback,
  type ReadyPracticeState,
  type UsePracticeSessionResult,
} from "../../features/practice/model/usePracticeSession";
import {
  CARD_COUNT_FORMS,
  CORRECT_ANSWER_COUNT_FORMS,
  MINUTE_SHORT_COUNT_FORMS,
  SECOND_SHORT_COUNT_FORMS,
  WRONG_ANSWER_COUNT_FORMS,
  formatNumber,
  localizeCount,
  useLocale,
  useLocalizedMessages,
  type AppLocale,
} from "../../i18n";
import styles from "./PracticePage.module.css";
import { usePracticeFullscreen } from "./usePracticeFullscreen";
import { PRACTICE_MESSAGES, type PracticeMessages } from "./PracticePage.messages";
import { CatalogDeckPreview } from "../CatalogPage/CatalogDeckPreview";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const practiceHistoryDateFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

type PracticeTextSize = "regular" | "medium" | "compact" | "dense";

function getFeedbackTextSize(text: string): PracticeTextSize {
  const normalizedText = text.trim();
  const characterCount = Array.from(normalizedText).length;
  const longestWordLength = normalizedText
    .split(/\s+/u)
    .reduce((longestLength, word) => Math.max(longestLength, Array.from(word).length), 0);

  if (characterCount <= 50) {
    return "regular";
  }
  if (characterCount > 110 || longestWordLength > 42) {
    return "dense";
  }
  if (characterCount > 64 || longestWordLength > 28) {
    return "compact";
  }

  return "medium";
}

function PracticePrompt({ language, text }: { language: string; text: string }) {
  const promptAreaRef = useRef<HTMLDivElement>(null);
  const promptRef = useRef<HTMLHeadingElement>(null);

  useLayoutEffect(() => {
    const promptArea = promptAreaRef.current;
    const prompt = promptRef.current;

    if (promptArea === null || prompt === null) {
      return;
    }

    const fitPrompt = () => {
      prompt.style.removeProperty("font-size");
      prompt.dataset.textSize = "regular";

      const promptAreaStyles = window.getComputedStyle(promptArea);
      const availableHeight =
        promptArea.clientHeight -
        Number.parseFloat(promptAreaStyles.paddingTop) -
        Number.parseFloat(promptAreaStyles.paddingBottom);
      const availableWidth =
        promptArea.clientWidth -
        Number.parseFloat(promptAreaStyles.paddingLeft) -
        Number.parseFloat(promptAreaStyles.paddingRight);

      const fitsAvailableArea = () => {
        const promptRect = prompt.getBoundingClientRect();
        return promptRect.height <= availableHeight + 1 && promptRect.width <= availableWidth + 1;
      };

      if (fitsAvailableArea()) {
        return;
      }

      const minimumFontSize = 12;
      let smallestFittingFontSize = minimumFontSize;
      let largestOverflowingFontSize = Number.parseFloat(window.getComputedStyle(prompt).fontSize);

      prompt.style.fontSize = `${minimumFontSize}px`;

      if (!fitsAvailableArea()) {
        return;
      }

      for (let attempt = 0; attempt < 10; attempt += 1) {
        const candidateFontSize = (smallestFittingFontSize + largestOverflowingFontSize) / 2;
        prompt.style.fontSize = `${candidateFontSize}px`;

        if (fitsAvailableArea()) {
          smallestFittingFontSize = candidateFontSize;
        } else {
          largestOverflowingFontSize = candidateFontSize;
        }
      }

      prompt.style.fontSize = `${Math.floor(smallestFittingFontSize * 100) / 100}px`;
    };

    fitPrompt();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", fitPrompt);
      return () => window.removeEventListener("resize", fitPrompt);
    }

    const resizeObserver = new ResizeObserver(fitPrompt);
    resizeObserver.observe(promptArea);

    return () => resizeObserver.disconnect();
  }, [text]);

  return (
    <div className={styles.promptArea} ref={promptAreaRef}>
      <h1 data-text-size="regular" id="practice-prompt" lang={language} ref={promptRef}>
        {text}
      </h1>
    </div>
  );
}

const PRACTICE_HISTORY_FILTERS: readonly PracticeHistoryFilter[] = [
  "all",
  "completed",
  "in_progress",
  "abandoned",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function ChevronIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d={direction === "left" ? "m14.5 6-6 6 6 6" : "m9.5 6 6 6-6 6"} />
    </svg>
  );
}

function FullscreenIcon({ active }: { active: boolean }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.7"
      viewBox="0 0 24 24"
    >
      <path
        d={active ? "M3 8h5V3m8 0v5h5M3 16h5v5m8 0v-5h5" : "M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"}
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d="m5.5 12.5 4 4 9-9" />
    </svg>
  );
}

function DirectionArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="3"
      viewBox="0 0 28 20"
    >
      <path d="M3 10h21" />
      <path d="m18 4 6 6-6 6" />
    </svg>
  );
}

function DirectionMark() {
  return (
    <span aria-hidden="true" className={styles.directionMark}>
      <DirectionArrowIcon />
    </span>
  );
}

function DirectionLabel({ from, to }: { from: string; to: string }) {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);

  return (
    <span aria-label={messages.directionLabel(from, to)} className={styles.directionLabel}>
      <span>{from}</span>
      <DirectionMark />
      <span>{to}</span>
    </span>
  );
}

function RepeatIcon() {
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
      <path d="M4.5 9A8 8 0 1 1 4 14" />
      <path d="M4.5 4v5h5" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2.15"
      viewBox="0 0 24 24"
    >
      <path d="M5.2 8.5A7.5 7.5 0 1 1 4.7 14" />
      <path d="M5.2 4.5v4h4M12 8.2v4.2l2.8 1.7" />
    </svg>
  );
}

function ResultIcon({ isCorrect }: { isCorrect: boolean }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      {isCorrect ? <path d="m5 12 4.2 4.2L19 6.5" /> : <path d="m7 7 10 10M17 7 7 17" />}
    </svg>
  );
}

function AmbientBackground() {
  return (
    <div aria-hidden="true" className={styles.ambient}>
      <span className={styles.ambientWash} />
      <span className={styles.ambientRule} />
      <span className={styles.ambientLetter}>Aa</span>
    </div>
  );
}

function getPracticeErrorMessage(
  error: unknown,
  operation: "resume" | "start" | "submit",
  messages: PracticeMessages,
): string {
  if (!isApiError(error)) {
    return messages.errors.default;
  }

  if (error.code === "INVALID_PRACTICE_RESPONSE") {
    return messages.errors.invalidResponse;
  }

  if (
    hasAnyApiErrorCode(error, [API_ERROR_CODES.deckNotFound, API_ERROR_CODES.deckPermissionDenied])
  ) {
    return messages.errors.deckNotFound;
  }
  if (
    hasAnyApiErrorCode(error, [
      API_ERROR_CODES.trainingSessionNotFound,
      API_ERROR_CODES.trainingSessionItemNotFound,
      API_ERROR_CODES.trainingSessionPermissionDenied,
    ])
  ) {
    return messages.errors.sessionNotFound;
  }
  if (hasApiErrorCode(error, API_ERROR_CODES.deckIsEmpty)) {
    return messages.errors.emptyDeck;
  }
  if (hasApiErrorCode(error, API_ERROR_CODES.trainingSessionAlreadyFinished)) {
    return operation === "resume"
      ? messages.errors.resumedFinished
      : messages.errors.submittedFinished;
  }
  if (hasApiErrorCode(error, API_ERROR_CODES.cardAlreadyAnswered)) {
    return messages.errors.alreadyAnswered;
  }
  if (hasApiErrorCode(error, API_ERROR_CODES.validationError)) {
    return operation === "submit" ? messages.errors.invalidAnswer : messages.errors.invalidLink;
  }

  // Ниже — ошибки без кода backend: сеть, отмена, шлюз и ещё не размеченные случаи.
  if (error.status === 403 || error.status === 404) {
    return operation === "start" ? messages.errors.deckNotFound : messages.errors.sessionNotFound;
  }
  if (error.status === 409) {
    if (operation === "start") {
      return messages.errors.emptyDeck;
    }
    return operation === "resume"
      ? messages.errors.resumedFinished
      : messages.errors.submittedFinished;
  }
  if (error.status === 422) {
    return operation === "submit" ? messages.errors.invalidAnswer : messages.errors.invalidLink;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.server;
  }

  return messages.errors.fallback;
}

function getPracticeDeckLoadErrorMessage(error: unknown, messages: PracticeMessages): string {
  if (isApiError(error) && error.code === "INVALID_PRACTICE_RESPONSE") {
    return messages.errors.invalidDeckResponse;
  }

  return getPracticeErrorMessage(error, "start", messages);
}

function getPracticeHistoryErrorMessage(error: unknown, messages: PracticeMessages): string {
  if (isApiError(error)) {
    if (error.code === "INVALID_PRACTICE_RESPONSE") {
      return messages.historyErrors.invalid;
    }
    if (error.status === 0) {
      return messages.historyErrors.network;
    }
    if (error.status >= 500) {
      return messages.historyErrors.server;
    }
  }

  return messages.historyErrors.default;
}

function getPracticeHistoryDateFormatter(locale: AppLocale): Intl.DateTimeFormat {
  const cachedFormatter = practiceHistoryDateFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
  practiceHistoryDateFormatters.set(locale, formatter);
  return formatter;
}

function formatPracticeHistoryDate(value: string, locale: AppLocale): string {
  return getPracticeHistoryDateFormatter(locale).format(new Date(value));
}

function getPracticeAccuracyToneClassName(accuracy: number): string {
  if (accuracy >= 91) {
    return styles.historyAccuracyPurple;
  }
  if (accuracy >= 81) {
    return styles.historyAccuracyTurquoise;
  }
  if (accuracy >= 71) {
    return styles.historyAccuracyGreen;
  }
  if (accuracy >= 61) {
    return styles.historyAccuracyYellow;
  }
  if (accuracy >= 51) {
    return styles.historyAccuracyOrange;
  }

  return styles.historyAccuracyRed;
}

function PracticeHistoryCard({
  isActionDisabled,
  isRepeating,
  locale,
  onContinue,
  onPreview,
  onRepeat,
  session,
}: {
  isActionDisabled: boolean;
  isRepeating: boolean;
  locale: AppLocale;
  onContinue: (session: PracticeHistorySession) => void;
  onPreview: (deckUuid: string, trigger: HTMLButtonElement) => void;
  onRepeat: (session: PracticeHistorySession) => void;
  session: PracticeHistorySession;
}) {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const canContinue = session.status === "in_progress";
  const canViewHistory = session.status === "completed" || session.status === "abandoned";
  const accuracy =
    session.answeredCount === 0
      ? 0
      : Math.min(100, Math.round((session.correctCount / session.answeredCount) * 100));
  const remainingCards = localizeCount(
    Math.max(session.requestedCount - session.answeredCount, 0),
    CARD_COUNT_FORMS,
    locale,
  ).text;

  return (
    <article className={styles.historyCard}>
      <header className={styles.historyCardHeader}>
        <time dateTime={session.startedAt}>
          {formatPracticeHistoryDate(session.startedAt, locale)}
        </time>
        <span className={styles[`historyStatus_${session.status}`]}>
          {messages.statuses[session.status]}
        </span>
      </header>

      {session.deckUuid === null ? (
        <p className={`${styles.historyDeck} ${styles.historyDeckDeleted}`}>
          <strong>
            {session.deckTitle === null
              ? messages.deletedDeck
              : `${session.deckTitle} · ${messages.deletedDeck}`}
          </strong>
        </p>
      ) : (
        <button
          aria-haspopup="dialog"
          aria-label={messages.previewDeck(session.deckTitle ?? messages.deletedDeck)}
          className={styles.historyDeck}
          onClick={(event) => {
            if (session.deckUuid !== null) onPreview(session.deckUuid, event.currentTarget);
          }}
          title={session.deckTitle ?? undefined}
          type="button"
        >
          <strong>{session.deckTitle}</strong>
        </button>
      )}

      {canContinue ? (
        <p className={styles.historyRemaining}>{messages.cardsRemaining(remainingCards)}</p>
      ) : null}

      <footer className={styles.historyCardFooter}>
        <dl className={styles.historyStats}>
          <div>
            <dt>{messages.correct}</dt>
            <dd>
              <strong>{formatNumber(session.correctCount, locale)}</strong>
              <span>/ {formatNumber(session.answeredCount, locale)}</span>
            </dd>
          </div>
          <div
            className={`${styles.historyAccuracyStat} ${getPracticeAccuracyToneClassName(accuracy)}`}
          >
            <dt>{messages.accuracy}</dt>
            <dd>{formatNumber(accuracy, locale)}%</dd>
          </div>
        </dl>

        <div
          className={
            canViewHistory
              ? styles.historyCardActions
              : `${styles.historyCardActions} ${styles.historyCardActionsSingle}`
          }
        >
          {canViewHistory ? (
            <Link
              aria-label={messages.openSessionHistory}
              className={styles.historyDetailsButton}
              title={messages.sessionHistory}
              to={`/practice/sessions/${session.uuid}/history`}
            >
              <HistoryIcon />
            </Link>
          ) : null}
          <button
            className={
              canContinue
                ? `${styles.historyRepeatButton} ${styles.historyRepeatButtonAccent}`
                : styles.historyRepeatButton
            }
            disabled={isActionDisabled || (!canContinue && session.deckUuid === null)}
            onClick={() => (canContinue ? onContinue(session) : onRepeat(session))}
            type="button"
          >
            {isRepeating ? <span className={styles.buttonSpinner} /> : null}
            {isRepeating ? messages.launching : canContinue ? messages.continue : messages.repeat}
          </button>
        </div>
      </footer>
    </article>
  );
}

function PracticeHistoryView({
  onContinue,
  onPreview,
  onRepeat,
  startError,
}: {
  onContinue: (session: PracticeHistorySession) => void;
  onPreview: (deckUuid: string, trigger: HTMLButtonElement) => void;
  onRepeat: (session: PracticeHistorySession) => Promise<void>;
  startError: unknown | null;
}) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const [activeFilter, setActiveFilter] = useState<PracticeHistoryFilter>("all");
  const history = usePracticeHistory(activeFilter);
  const [repeatingSessionUuid, setRepeatingSessionUuid] = useState<string | null>(null);
  const historyFiltersRef = useRef<HTMLDivElement | null>(null);
  const historyFilterButtonRefs = useRef(new Map<PracticeHistoryFilter, HTMLButtonElement>());

  useLayoutEffect(() => {
    const filters = historyFiltersRef.current;
    const activeButton = historyFilterButtonRefs.current.get(activeFilter);
    if (filters === null || activeButton === undefined) {
      return;
    }

    const updateIndicator = (): void => {
      const x = activeButton.offsetLeft;
      const y = activeButton.offsetTop;
      const width = activeButton.offsetWidth;
      const height = activeButton.offsetHeight;

      filters.style.setProperty("--history-filter-indicator-x", `${x}px`);
      filters.style.setProperty("--history-filter-indicator-y", `${y}px`);
      filters.style.setProperty("--history-filter-indicator-width", `${width}px`);
      filters.style.setProperty("--history-filter-indicator-height", `${height}px`);
      filters.dataset.indicatorReady = "true";
    };

    updateIndicator();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateIndicator);
      return () => window.removeEventListener("resize", updateIndicator);
    }

    const resizeObserver = new ResizeObserver(updateIndicator);
    resizeObserver.observe(filters);
    historyFilterButtonRefs.current.forEach((button) => resizeObserver.observe(button));
    return () => resizeObserver.disconnect();
  }, [activeFilter]);

  const sessions = history.state.status === "ready" ? history.state.sessions : [];

  const handleRepeat = async (session: PracticeHistorySession) => {
    if (repeatingSessionUuid !== null) {
      return;
    }

    setRepeatingSessionUuid(session.uuid);
    try {
      await onRepeat(session);
    } finally {
      setRepeatingSessionUuid(null);
    }
  };

  let historyContent;
  if (history.state.status === "loading") {
    historyContent = (
      <div aria-label={messages.loadingHistory} className={styles.historySkeletons} role="status">
        <span />
        <span />
        <span />
      </div>
    );
  } else if (history.state.status === "error") {
    historyContent = (
      <div className={styles.historyMessage} role="alert">
        <strong>{messages.historyUnavailable}</strong>
        <p>{getPracticeHistoryErrorMessage(history.state.error, messages)}</p>
        <button className={styles.secondaryAction} onClick={history.retry} type="button">
          {messages.retry}
        </button>
      </div>
    );
  } else if (sessions.length === 0) {
    historyContent = (
      <div className={styles.historyMessage}>
        <div aria-hidden="true" className={styles.historyEmptyVisual}>
          <span>Aa</span>
          <span>Бб</span>
        </div>
        <strong>
          {activeFilter === "all" ? messages.emptyHistory : messages.emptyFilteredHistory}
        </strong>
        {activeFilter === "all" ? (
          <Link className={styles.primaryAction} to="/library">
            {messages.chooseDeck}
          </Link>
        ) : null}
      </div>
    );
  } else {
    historyContent = (
      <div className={styles.historyGrid}>
        {sessions.map((session) => (
          <PracticeHistoryCard
            isActionDisabled={repeatingSessionUuid !== null}
            isRepeating={repeatingSessionUuid === session.uuid}
            key={session.uuid}
            locale={locale}
            onContinue={onContinue}
            onPreview={onPreview}
            onRepeat={(selectedSession) => void handleRepeat(selectedSession)}
            session={session}
          />
        ))}
      </div>
    );
  }

  return (
    <main className={styles.historyMain}>
      <section className={styles.historyPanel}>
        <header className={styles.historyIntro}>
          <h1>{messages.practiceTitle}</h1>
          <Link className={styles.primaryAction} to="/library">
            <span>{messages.newSession}</span>
            <DashboardIcon name="plus" />
          </Link>
        </header>

        <div className={styles.historyToolbar}>
          <div className={styles.historyHeading}>
            <h2>{messages.sessionsTitle}</h2>
            <p>{messages.sessionsLead}</p>
          </div>

          <div
            aria-label={messages.historyFilters}
            className={styles.historyFilters}
            data-active-filter={activeFilter}
            ref={historyFiltersRef}
            role="group"
          >
            <span aria-hidden="true" className={styles.historyFilterIndicator} />
            {PRACTICE_HISTORY_FILTERS.map((filter) => (
              <button
                aria-pressed={activeFilter === filter}
                className={
                  activeFilter === filter
                    ? `${styles.historyFilter} ${styles.historyFilterActive}`
                    : styles.historyFilter
                }
                key={filter}
                onClick={() => setActiveFilter(filter)}
                ref={(button) => {
                  if (button === null) {
                    historyFilterButtonRefs.current.delete(filter);
                  } else {
                    historyFilterButtonRefs.current.set(filter, button);
                  }
                }}
                type="button"
              >
                {messages.filters[filter]}
              </button>
            ))}
          </div>
        </div>

        {startError === null ? null : (
          <p className={styles.historyStartError} role="alert">
            {getPracticeErrorMessage(startError, "start", messages)}
          </p>
        )}

        <div aria-live="polite" className={styles.historyContent}>
          {historyContent}
        </div>
      </section>
    </main>
  );
}

interface SetupViewProps {
  deckUuid: string;
  deckWordsCount: number;
  practice: UsePracticeSessionResult;
  onStarted: (session: PracticeSession) => void;
}

export function PracticeSetupView({
  deckUuid,
  deckWordsCount,
  onStarted,
  practice,
}: SetupViewProps) {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const customCountHintId = useId();
  const [promptSide, setPromptSide] = useState<CardSide>("front");
  const [sessionScope, setSessionScope] = useState<PracticeSessionScope>("all");
  const [customWordsCount, setCustomWordsCount] = useState("");
  const isStarting = practice.state.status === "loading" && practice.state.operation === "start";
  const wordsPerSession = getWordsPerSession(sessionScope, deckWordsCount, customWordsCount);
  const customSessionSize = readCustomSessionSize(customWordsCount);
  const isCustomCountInvalid = sessionScope === "custom" && customSessionSize.isInvalid;
  const startError =
    practice.state.status === "error" && practice.state.operation === "start"
      ? practice.state.error
      : null;

  const handleStart = async () => {
    if (wordsPerSession === null) {
      return;
    }

    const session = await practice.start(deckUuid, promptSide, wordsPerSession);
    if (session !== null) {
      onStarted(session);
    }
  };

  return (
    <main className={styles.centeredMain}>
      <section aria-busy={isStarting} className={styles.setupPanel}>
        <header className={styles.setupIntro}>
          <h1>{messages.setupTitle}</h1>
        </header>

        <div className={styles.setupWorkspace}>
          <div className={styles.settingsCard}>
            <fieldset className={styles.settingGroup} disabled={isStarting}>
              <legend>{messages.direction}</legend>
              <div className={styles.sideOptions} data-active={promptSide}>
                <span aria-hidden="true" className={styles.sideOptionThumb} />
                <label
                  className={
                    promptSide === "front"
                      ? `${styles.sideOption} ${styles.sideOptionSelected}`
                      : styles.sideOption
                  }
                >
                  <input
                    checked={promptSide === "front"}
                    name="prompt_side"
                    onChange={() => setPromptSide("front")}
                    type="radio"
                    value="front"
                  />
                  <DirectionLabel from={messages.translation} to={messages.wordLower} />
                </label>

                <label
                  className={
                    promptSide === "back"
                      ? `${styles.sideOption} ${styles.sideOptionSelected}`
                      : styles.sideOption
                  }
                >
                  <input
                    checked={promptSide === "back"}
                    name="prompt_side"
                    onChange={() => setPromptSide("back")}
                    type="radio"
                    value="back"
                  />
                  <DirectionLabel from={messages.word} to={messages.translationLower} />
                </label>
              </div>
            </fieldset>

            <fieldset
              className={`${styles.settingGroup} ${styles.scopeGroup}`}
              disabled={isStarting}
            >
              <legend>{messages.scope}</legend>
              <div className={styles.scopeOptions}>
                <label
                  className={
                    sessionScope === "all"
                      ? `${styles.scopeOption} ${styles.scopeOptionSelected}`
                      : styles.scopeOption
                  }
                >
                  <input
                    checked={sessionScope === "all"}
                    name="session_scope"
                    onChange={() => setSessionScope("all")}
                    type="radio"
                    value="all"
                  />
                  <span>
                    {canPracticeEntireDeck(deckWordsCount)
                      ? messages.entireDeck
                      : messages.maxCards(MAX_SESSION_SIZE)}
                  </span>
                </label>
                <label
                  className={
                    sessionScope === "50"
                      ? `${styles.scopeOption} ${styles.scopeOptionSelected}`
                      : styles.scopeOption
                  }
                >
                  <input
                    checked={sessionScope === "50"}
                    name="session_scope"
                    onChange={() => setSessionScope("50")}
                    type="radio"
                    value="50"
                  />
                  <span>{messages.fiftyCards}</span>
                </label>
                <label
                  className={
                    sessionScope === "100"
                      ? `${styles.scopeOption} ${styles.scopeOptionSelected}`
                      : styles.scopeOption
                  }
                >
                  <input
                    checked={sessionScope === "100"}
                    name="session_scope"
                    onChange={() => setSessionScope("100")}
                    type="radio"
                    value="100"
                  />
                  <span>{messages.hundredCards}</span>
                </label>
                <label
                  className={[
                    styles.scopeOption,
                    styles.customScopeOption,
                    sessionScope === "custom" ? styles.scopeOptionSelected : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <input
                    checked={sessionScope === "custom"}
                    name="session_scope"
                    onChange={() => setSessionScope("custom")}
                    type="radio"
                    value="custom"
                  />
                  <span>{messages.customCount}</span>
                  <input
                    aria-describedby={customCountHintId}
                    aria-label={messages.cardCount}
                    aria-invalid={isCustomCountInvalid ? true : undefined}
                    className={
                      isCustomCountInvalid
                        ? `${styles.scopeInput} ${styles.scopeInputInvalid}`
                        : styles.scopeInput
                    }
                    max={MAX_SESSION_SIZE}
                    min="1"
                    onBlur={() => setCustomWordsCount(clampCustomSessionSize(customWordsCount))}
                    onChange={(event) => setCustomWordsCount(event.target.value)}
                    onFocus={() => setSessionScope("custom")}
                    step="1"
                    type="number"
                    value={customWordsCount}
                  />
                </label>
              </div>

              <p
                className={
                  isCustomCountInvalid
                    ? `${styles.scopeHint} ${styles.scopeHintInvalid}`
                    : styles.scopeHint
                }
                id={customCountHintId}
              >
                {messages.sessionSizeRange(MAX_SESSION_SIZE)}
              </p>
            </fieldset>
          </div>

          <section aria-atomic="true" aria-live="polite" className={styles.setupPreview}>
            <h2>{messages.example}</h2>

            <div className={styles.previewCard}>
              <div className={styles.previewStage}>
                <span className={styles.previewLabel}>{messages.youWillSee}</span>
                <strong className={styles.previewWord}>
                  {promptSide === "front" ? "язык" : "language"}
                </strong>
              </div>

              <div aria-hidden="true" className={styles.previewFlow}>
                <DirectionMark />
              </div>

              <div className={`${styles.previewStage} ${styles.previewAnswer}`}>
                <span className={styles.previewLabel}>{messages.youWillType}</span>
                <div className={styles.previewInput}>
                  <span>{promptSide === "front" ? "language" : "язык"}</span>
                  <i aria-hidden="true" />
                </div>
              </div>
            </div>
          </section>
        </div>

        <div className={styles.setupBottom}>
          {startError === null ? null : (
            <p className={styles.inlineError} role="alert">
              {getPracticeErrorMessage(startError, "start", messages)}
            </p>
          )}

          <div className={styles.setupFooter}>
            <Link className={styles.secondaryAction} to="/library">
              {messages.back}
            </Link>
            <button
              className={styles.primaryAction}
              disabled={isStarting || wordsPerSession === null}
              onClick={() => void handleStart()}
              type="button"
            >
              {isStarting ? <span className={styles.buttonSpinner} /> : null}
              {isStarting ? messages.preparing : messages.start}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

function SessionLoadingView({ ariaLabel, message }: { ariaLabel?: string; message?: string }) {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);

  return (
    <main className={styles.sessionMain}>
      <div
        aria-label={ariaLabel ?? messages.loadingSession}
        className={styles.sessionLoader}
        role="status"
      >
        <span className={styles.loaderCore} />
        <p>{message ?? messages.loading}</p>
      </div>
    </main>
  );
}

function SessionErrorView({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const isFinishedSession = isApiError(error) && error.status === 409;
  const isMissingSession = isApiError(error) && (error.status === 403 || error.status === 404);
  const isInvalidSessionLink = isApiError(error) && error.status === 422;
  const canRetry = !isFinishedSession && !isMissingSession && !isInvalidSessionLink;
  const title = isMissingSession
    ? messages.sessionNotFoundTitle
    : isFinishedSession
      ? messages.sessionFinishedTitle
      : isInvalidSessionLink
        ? messages.invalidLinkTitle
        : messages.resumeFailedTitle;

  return (
    <main className={styles.centeredMain}>
      <section className={`${styles.paperPanel} ${styles.errorPanel}`} role="alert">
        <h1>{title}</h1>
        <p>{getPracticeErrorMessage(error, "resume", messages)}</p>
        <div className={styles.errorActions}>
          {canRetry ? (
            <button className={styles.primaryAction} onClick={onRetry} type="button">
              {messages.retry}
            </button>
          ) : null}
          <Link className={styles.secondaryAction} to="/library">
            {isFinishedSession ? messages.chooseNewPractice : messages.toLibrary}
          </Link>
        </div>
      </section>
    </main>
  );
}

function PracticeDeckNotFoundView() {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);

  return (
    <main className={styles.centeredMain}>
      <section className={`${styles.paperPanel} ${styles.errorPanel}`} role="alert">
        <h1>{messages.deckNotFoundTitle}</h1>
        <p>{messages.deckNotFoundLead}</p>
        <div className={styles.errorActions}>
          <Link className={styles.primaryAction} to="/library">
            {messages.chooseAnotherDeck}
          </Link>
          <Link className={styles.secondaryAction} to="/">
            {messages.home}
          </Link>
        </div>
      </section>
    </main>
  );
}

function PracticeDeckLoadErrorView({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);

  return (
    <main className={styles.centeredMain}>
      <section className={`${styles.paperPanel} ${styles.errorPanel}`} role="alert">
        <h1>{messages.deckLoadFailedTitle}</h1>
        <p>{getPracticeDeckLoadErrorMessage(error, messages)}</p>
        <div className={styles.errorActions}>
          <button className={styles.primaryAction} onClick={onRetry} type="button">
            {messages.retry}
          </button>
          <Link className={styles.secondaryAction} to="/library">
            {messages.toLibrary}
          </Link>
        </div>
      </section>
    </main>
  );
}

function formatLanguage(language: string, locale: AppLocale): string {
  return language.trim().toLocaleUpperCase(locale);
}

function formatDuration(totalSeconds: number | null, locale: AppLocale): string {
  if (totalSeconds === null) {
    return "—";
  }

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) {
    return localizeCount(seconds, SECOND_SHORT_COUNT_FORMS, locale).text;
  }

  const localizedMinutes = localizeCount(minutes, MINUTE_SHORT_COUNT_FORMS, locale);
  const localizedSeconds = localizeCount(seconds, SECOND_SHORT_COUNT_FORMS, locale);
  const paddedSeconds = formatNumber(seconds, locale).padStart(2, "0");

  return `${localizedMinutes.text} ${paddedSeconds} ${localizedSeconds.unit}`;
}

function getNextUnansweredSequenceNumber(
  cards: readonly PracticeCard[],
  currentSequenceNumber: number,
  feedbackBySequence: Readonly<Record<number, PracticeCardFeedback>>,
): number | null {
  const currentIndex = cards.findIndex((card) => card.sequenceNumber === currentSequenceNumber);
  const startingIndex = currentIndex >= 0 ? currentIndex : 0;

  for (let offset = 1; offset <= cards.length; offset += 1) {
    const card = cards[(startingIndex + offset) % cards.length];
    if (card !== undefined && feedbackBySequence[card.sequenceNumber] === undefined) {
      return card.sequenceNumber;
    }
  }

  return null;
}

export interface PracticeCompletionSummary {
  sessionUuid: string;
  deckUuid: string | null;
  totalCount: number;
  correctCount: number;
  wrongCount: number;
  timeToCompleteSeconds: number | null;
}

interface CompletionViewProps {
  summary: PracticeCompletionSummary;
}

function createCompletionSummary(
  session: PracticeSession,
  timeToCompleteSeconds: number | null,
): PracticeCompletionSummary {
  return {
    sessionUuid: session.uuid,
    deckUuid: session.deckUuid,
    totalCount: session.totalCount,
    correctCount: session.correctCount,
    wrongCount: session.wrongCount,
    timeToCompleteSeconds,
  };
}

function readCompletionSummary(value: unknown): PracticeCompletionSummary | null {
  if (!isRecord(value)) {
    return null;
  }

  const summary = value.practiceCompletion;
  if (!isRecord(summary)) {
    return null;
  }

  const { correctCount, deckUuid, sessionUuid, timeToCompleteSeconds, totalCount, wrongCount } =
    summary;
  if (
    typeof sessionUuid !== "string" ||
    !UUID_PATTERN.test(sessionUuid) ||
    (deckUuid !== null && (typeof deckUuid !== "string" || !UUID_PATTERN.test(deckUuid))) ||
    typeof totalCount !== "number" ||
    !Number.isInteger(totalCount) ||
    totalCount < 1 ||
    typeof correctCount !== "number" ||
    !Number.isInteger(correctCount) ||
    correctCount < 0 ||
    typeof wrongCount !== "number" ||
    !Number.isInteger(wrongCount) ||
    wrongCount < 0 ||
    correctCount + wrongCount !== totalCount ||
    (timeToCompleteSeconds !== null &&
      (typeof timeToCompleteSeconds !== "number" ||
        !Number.isInteger(timeToCompleteSeconds) ||
        timeToCompleteSeconds < 0))
  ) {
    return null;
  }

  return {
    correctCount,
    deckUuid: deckUuid === null ? null : deckUuid.toLowerCase(),
    sessionUuid: sessionUuid.toLowerCase(),
    timeToCompleteSeconds,
    totalCount,
    wrongCount,
  };
}

export function PracticeCompletionView({ summary }: CompletionViewProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const panelRef = useRef<HTMLElement>(null);
  const accuracy = Math.round((summary.correctCount / summary.totalCount) * 100);

  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  return (
    <main className={styles.centeredMain}>
      <section
        className={`${styles.paperPanel} ${styles.completionPanel}`}
        ref={panelRef}
        tabIndex={-1}
      >
        <div className={styles.completionHalo}>
          <span>{accuracy}%</span>
        </div>
        <h1>{messages.deckCompleted}</h1>

        <dl className={styles.completionStats}>
          <div>
            <dt>{messages.correct}</dt>
            <dd>{summary.correctCount}</dd>
          </div>
          <div>
            <dt>{messages.errorsLabel}</dt>
            <dd>{summary.wrongCount}</dd>
          </div>
          <div>
            <dt>{messages.time}</dt>
            <dd>{formatDuration(summary.timeToCompleteSeconds, locale)}</dd>
          </div>
        </dl>

        <div className={styles.completionActions}>
          {summary.deckUuid !== null ? (
            <Link className={styles.primaryAction} to={`/practice?deck=${summary.deckUuid}`}>
              <RepeatIcon />
              {messages.again}
            </Link>
          ) : null}
          <Link className={styles.secondaryAction} to="/library">
            {messages.toLibrary}
          </Link>
        </div>
      </section>
    </main>
  );
}

interface SessionProgressProps {
  session: PracticeSession;
}

function SessionProgress({ session }: SessionProgressProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const progress = Math.round((session.answeredCount / session.totalCount) * 100);
  const correctAnswerCount = localizeCount(
    session.correctCount,
    CORRECT_ANSWER_COUNT_FORMS,
    locale,
  );
  const wrongAnswerCount = localizeCount(session.wrongCount, WRONG_ANSWER_COUNT_FORMS, locale);

  return (
    <div className={styles.progressPanel}>
      <div className={styles.progressCopy}>
        <strong>
          {session.answeredCount} <small>/ {session.totalCount}</small>
        </strong>
      </div>
      <div
        aria-label={messages.progress(session.answeredCount, session.totalCount)}
        aria-valuemax={session.totalCount}
        aria-valuemin={0}
        aria-valuenow={session.answeredCount}
        className={styles.progressTrack}
        role="progressbar"
      >
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className={styles.scoreChips}>
        <span aria-label={correctAnswerCount.text} className={styles.correctChip}>
          <span aria-hidden="true">✓ {session.correctCount}</span>
        </span>
        <span aria-label={wrongAnswerCount.text} className={styles.wrongChip}>
          <span aria-hidden="true">× {session.wrongCount}</span>
        </span>
      </div>
    </div>
  );
}

interface CardPaginationProps {
  cards: readonly PracticeCard[];
  currentSequenceNumber: number;
  feedbackBySequence: Readonly<Record<number, PracticeCardFeedback>>;
  isDisabled: boolean;
  onSelect: (sequenceNumber: number) => void;
}

function CardPagination({
  cards,
  currentSequenceNumber,
  feedbackBySequence,
  isDisabled,
  onSelect,
}: CardPaginationProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const sequenceNumbers = cards.map((card) => card.sequenceNumber);
  const tokens = getPracticePaginationTokens(sequenceNumbers, currentSequenceNumber, locale);
  const currentIndex = sequenceNumbers.indexOf(currentSequenceNumber);
  const previousSequenceNumber = currentIndex > 0 ? sequenceNumbers[currentIndex - 1] : undefined;
  const nextSequenceNumber =
    currentIndex >= 0 && currentIndex < sequenceNumbers.length - 1
      ? sequenceNumbers[currentIndex + 1]
      : undefined;

  return (
    <nav aria-label={messages.sessionCards} className={styles.pagination}>
      <button
        aria-label={messages.previousCard}
        className={styles.paginationArrow}
        disabled={isDisabled || previousSequenceNumber === undefined}
        onClick={() => previousSequenceNumber !== undefined && onSelect(previousSequenceNumber)}
        type="button"
      >
        <ChevronIcon direction="left" />
      </button>

      <div className={styles.pageNumbers}>
        {tokens.map((token) => {
          if (token.type === "ellipsis") {
            return (
              <span
                aria-label={token.ariaLabel}
                className={styles.paginationEllipsis}
                key={token.key}
              >
                {token.label}
              </span>
            );
          }

          const feedback = feedbackBySequence[token.sequenceNumber];
          const stateClassName =
            feedback === undefined
              ? ""
              : feedback.isCorrect
                ? styles.pageNumberCorrect
                : styles.pageNumberWrong;
          const feedbackLabel =
            feedback === undefined
              ? null
              : feedback.isCorrect
                ? messages.correctAnswer
                : messages.wrongAnswer;
          const className = [
            styles.pageNumber,
            token.isCurrent ? styles.pageNumberCurrent : "",
            stateClassName,
          ]
            .filter(Boolean)
            .join(" ");

          return (
            <button
              aria-current={token.isCurrent ? "page" : undefined}
              aria-label={
                feedbackLabel === null ? token.ariaLabel : `${token.ariaLabel}. ${feedbackLabel}`
              }
              className={className}
              disabled={isDisabled}
              key={token.key}
              onClick={() => onSelect(token.sequenceNumber)}
              type="button"
            >
              {token.label}
            </button>
          );
        })}
      </div>

      <button
        aria-label={messages.nextCard}
        className={styles.paginationArrow}
        disabled={isDisabled || nextSequenceNumber === undefined}
        onClick={() => nextSequenceNumber !== undefined && onSelect(nextSequenceNumber)}
        type="button"
      >
        <ChevronIcon direction="right" />
      </button>
    </nav>
  );
}

interface AnswerAreaProps {
  card: PracticeCard;
  feedback: PracticeCardFeedback | undefined;
  isFinished: boolean;
  isSubmitting: boolean;
  nextSequenceNumber: number | null;
  submitError: unknown | null;
  value: string;
  onChange: (value: string) => void;
  onContinue: () => void;
  onFinish: () => void;
  onSkip: () => void;
  onSubmit: () => void;
}

function AnswerArea({
  card,
  feedback,
  isFinished,
  isSubmitting,
  nextSequenceNumber,
  onChange,
  onContinue,
  onFinish,
  onSkip,
  onSubmit,
  submitError,
  value,
}: AnswerAreaProps) {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const inputId = useId();
  const answerInputRef = useRef<HTMLTextAreaElement>(null);
  const continueButtonRef = useRef<HTMLButtonElement>(null);
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (value.trim()) {
      onSubmit();
    }
  };

  useEffect(() => {
    if (feedback !== undefined) {
      continueButtonRef.current?.focus();
    }
  }, [feedback]);

  useEffect(() => {
    const input = answerInputRef.current;
    if (input === null) {
      return;
    }

    const resizeInput = (): void => {
      const maximumHeight = 54;
      input.style.height = "0px";
      const nextHeight = Math.min(Math.max(input.scrollHeight, 54), maximumHeight);
      input.style.height = `${nextHeight}px`;
      input.style.overflowY = input.scrollHeight > maximumHeight ? "auto" : "hidden";
    };

    resizeInput();
    window.addEventListener("resize", resizeInput);
    return () => window.removeEventListener("resize", resizeInput);
  }, [value]);

  const feedbackText =
    feedback === undefined
      ? null
      : feedback.isCorrect
        ? feedback.answerText
        : messages.correctAnswerText(feedback.answerText);

  const liveMessage =
    feedback === undefined
      ? submitError === null
        ? ""
        : getPracticeErrorMessage(submitError, "submit", messages)
      : feedback.isCorrect
        ? messages.correctLiveMessage(feedback.answerText)
        : messages.wrongLiveMessage(feedback.answerText);

  if (feedback !== undefined) {
    return (
      <div className={styles.answerRegion}>
        <span aria-atomic="true" aria-live="polite" className={styles.visuallyHidden}>
          {liveMessage}
        </span>
        <div
          className={`${styles.feedback} ${feedback.isCorrect ? styles.feedbackCorrect : styles.feedbackWrong}`}
        >
          <span className={styles.feedbackIcon}>
            <ResultIcon isCorrect={feedback.isCorrect} />
          </span>
          <div className={styles.feedbackCopy}>
            <strong>
              {feedback.isCorrect ? messages.correctFeedback : messages.wrongFeedback}
            </strong>
            <span
              className={styles.feedbackAnswer}
              data-text-size={getFeedbackTextSize(feedbackText ?? "")}
            >
              {feedbackText}
            </span>
          </div>
          <button
            className={styles.continueButton}
            data-practice-primary-focus
            onClick={isFinished || nextSequenceNumber === null ? onFinish : onContinue}
            ref={continueButtonRef}
            type="button"
          >
            {isFinished || nextSequenceNumber === null ? messages.result : messages.next}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.answerRegion}>
      <span aria-atomic="true" aria-live="polite" className={styles.visuallyHidden}>
        {liveMessage}
      </span>
      <form className={styles.answerForm} onSubmit={handleSubmit}>
        <label className={styles.answerLabel} htmlFor={inputId}>
          {messages.yourAnswer}
        </label>
        <div className={styles.answerControls}>
          <textarea
            autoComplete="off"
            autoFocus
            data-practice-primary-focus
            disabled={isSubmitting}
            id={inputId}
            lang={card.answerLanguage}
            maxLength={255}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                if (!isSubmitting && value.trim()) {
                  event.currentTarget.form?.requestSubmit();
                }
              }
            }}
            placeholder={messages.yourAnswer}
            ref={answerInputRef}
            rows={1}
            value={value}
          />
          <button
            aria-label={messages.submitAnswer}
            className={styles.submitButton}
            disabled={isSubmitting || !value.trim()}
            type="submit"
          >
            {isSubmitting ? <span className={styles.buttonSpinner} /> : <CheckIcon />}
          </button>
        </div>
        <div className={styles.answerMeta}>
          <button disabled={isSubmitting} onClick={onSkip} type="button">
            {messages.doNotKnow}
          </button>
        </div>
        {submitError === null ? null : (
          <p className={styles.submitError}>
            {getPracticeErrorMessage(submitError, "submit", messages)}
          </p>
        )}
      </form>
    </div>
  );
}

interface ActiveSessionViewProps {
  activity?: Pick<UsePracticeActivityResult, "focusRevision" | "phase" | "resume">;
  state: ReadyPracticeState;
  onSubmit: UsePracticeSessionResult["submit"];
  onComplete: (summary: PracticeCompletionSummary) => void;
}

const DEFAULT_ACTIVITY_VIEW = {
  focusRevision: 0,
  phase: "active",
  resume: () => undefined,
} as const;

export function ActivePracticeSessionView({
  activity = DEFAULT_ACTIVITY_VIEW,
  onComplete,
  onSubmit,
  state,
}: ActiveSessionViewProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const { isFullscreen, sessionRef, toggleFullscreen } = usePracticeFullscreen();
  const [selectedSequenceNumber, setSelectedSequenceNumber] = useState(
    state.session.cards[0]?.sequenceNumber ?? 1,
  );
  const [draftsBySequence, setDraftsBySequence] = useState<Readonly<Record<number, string>>>({});

  useEffect(() => {
    if (activity.phase !== "active" || activity.focusRevision === 0) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      workspaceRef.current
        ?.querySelector<HTMLElement>("[data-practice-primary-focus]:not(:disabled)")
        ?.focus();
    });

    return () => window.cancelAnimationFrame(frame);
  }, [activity.focusRevision, activity.phase]);

  const selectedCard =
    state.session.cards.find((card) => card.sequenceNumber === selectedSequenceNumber) ??
    state.session.cards[0];

  if (selectedCard === undefined) {
    return <SessionLoadingView />;
  }

  const feedback = state.feedbackBySequence[selectedCard.sequenceNumber];
  const isSubmitting = state.submittingSequenceNumber !== null;
  const nextSequenceNumber = getNextUnansweredSequenceNumber(
    state.session.cards,
    selectedCard.sequenceNumber,
    state.feedbackBySequence,
  );
  const draft = draftsBySequence[selectedCard.sequenceNumber] ?? "";
  const cardClassName = [
    styles.practiceCard,
    feedback === undefined
      ? ""
      : feedback.isCorrect
        ? styles.practiceCardCorrect
        : styles.practiceCardWrong,
  ]
    .filter(Boolean)
    .join(" ");

  const setDraft = (value: string) => {
    setDraftsBySequence((currentDrafts) => ({
      ...currentDrafts,
      [selectedCard.sequenceNumber]: value,
    }));
  };

  return (
    <main
      className={styles.sessionMain}
      data-session-fullscreen={isFullscreen ? "true" : undefined}
      ref={sessionRef}
    >
      <div className={styles.sessionToolbar}>
        <SessionProgress session={state.session} />
        <button
          aria-label={isFullscreen ? messages.exitFullscreen : messages.enterFullscreen}
          aria-pressed={isFullscreen}
          className={styles.fullscreenButton}
          onClick={toggleFullscreen}
          title={isFullscreen ? messages.exitFullscreen : messages.enterFullscreen}
          type="button"
        >
          <FullscreenIcon active={isFullscreen} />
          <span>{isFullscreen ? messages.exitFullscreen : messages.enterFullscreen}</span>
        </button>
      </div>
      <div
        aria-hidden={activity.phase === "paused" ? true : undefined}
        className={
          activity.phase === "paused"
            ? `${styles.sessionActivityContent} ${styles.sessionActivityContentPaused}`
            : styles.sessionActivityContent
        }
        inert={activity.phase === "paused" ? true : undefined}
        ref={workspaceRef}
      >
        <section aria-labelledby="practice-prompt" className={styles.cardStage}>
          <article className={cardClassName} key={selectedCard.sequenceNumber}>
            <div className={styles.cardTopline}>
              <span
                aria-label={messages.card(selectedCard.sequenceNumber)}
                className={styles.cardNumber}
              >
                {String(selectedCard.sequenceNumber).padStart(2, "0")}
              </span>
              <span
                aria-label={messages.languageFlow(
                  selectedCard.promptLanguage,
                  selectedCard.answerLanguage,
                )}
                className={styles.languageFlow}
              >
                <span>{formatLanguage(selectedCard.promptLanguage, locale)}</span>
                <DirectionMark />
                <span>{formatLanguage(selectedCard.answerLanguage, locale)}</span>
              </span>
            </div>

            <PracticePrompt language={selectedCard.promptLanguage} text={selectedCard.promptText} />

            <AnswerArea
              card={selectedCard}
              feedback={feedback}
              isFinished={state.isFinished}
              isSubmitting={isSubmitting}
              nextSequenceNumber={nextSequenceNumber}
              onChange={setDraft}
              onContinue={() =>
                nextSequenceNumber !== null && setSelectedSequenceNumber(nextSequenceNumber)
              }
              onFinish={() =>
                onComplete(createCompletionSummary(state.session, state.timeToCompleteSeconds))
              }
              onSkip={() => void onSubmit(selectedCard.sequenceNumber, { action: "skip" })}
              onSubmit={() =>
                void onSubmit(selectedCard.sequenceNumber, {
                  action: "answer",
                  answer: draft.trim(),
                })
              }
              submitError={
                state.submitError?.sequenceNumber === selectedCard.sequenceNumber
                  ? state.submitError.error
                  : null
              }
              value={draft}
            />
          </article>

          <CardPagination
            cards={state.session.cards}
            currentSequenceNumber={selectedCard.sequenceNumber}
            feedbackBySequence={state.feedbackBySequence}
            isDisabled={isSubmitting}
            onSelect={setSelectedSequenceNumber}
          />
        </section>
      </div>

      {activity.phase === "paused" ? (
        <button
          aria-label={`${messages.activityPaused}. ${messages.activityPausedHint}`}
          autoFocus
          className={styles.pausedOverlay}
          onClick={activity.resume}
          type="button"
        >
          <span className={styles.pausedOverlayContent}>
            <span aria-hidden="true" className={styles.pauseSymbol}>
              <i />
              <i />
            </span>
            <strong>{messages.activityPaused}</strong>
            <span>{messages.activityPausedHint}</span>
          </span>
        </button>
      ) : null}
    </main>
  );
}

interface TrackedActivePracticeSessionViewProps extends Omit<ActiveSessionViewProps, "activity"> {
  onSessionUnavailable: () => void;
}

function TrackedActivePracticeSessionView({
  onComplete,
  onSessionUnavailable,
  onSubmit,
  state,
}: TrackedActivePracticeSessionViewProps) {
  const activity = usePracticeActivity({
    enabled: !state.isFinished,
    onSessionUnavailable,
    sessionUuid: state.session.uuid,
  });
  const handleSubmit: UsePracticeSessionResult["submit"] = async (sequenceNumber, input) => {
    const result = await onSubmit(sequenceNumber, input);
    if (result !== null) {
      activity.noteAnswerAccepted(result.isFinished);
    }
    return result;
  };

  return (
    <ActivePracticeSessionView
      activity={activity}
      onComplete={onComplete}
      onSubmit={handleSubmit}
      state={state}
    />
  );
}

function InvalidPracticeLinkView() {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);

  return (
    <main className={styles.centeredMain}>
      <section className={`${styles.paperPanel} ${styles.errorPanel}`} role="alert">
        <h1>{messages.invalidLinkTitle}</h1>
        <p>{messages.invalidLinkLead}</p>
        <Link className={styles.primaryAction} to="/library">
          {messages.goToLibrary}
        </Link>
      </section>
    </main>
  );
}

export function PracticePage() {
  const messages = useLocalizedMessages(PRACTICE_MESSAGES);
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const deckQuery = searchParams.get("deck");
  const sessionQuery = searchParams.get("session");
  const previewQuery = searchParams.get("preview");
  const hasConflictingQuery = deckQuery !== null && sessionQuery !== null;
  const isDeckQueryValid = deckQuery === null || UUID_PATTERN.test(deckQuery);
  const isSessionQueryValid = sessionQuery === null || UUID_PATTERN.test(sessionQuery);
  const deckUuid =
    !hasConflictingQuery && isDeckQueryValid && deckQuery !== null ? deckQuery.toLowerCase() : null;
  const sessionUuid =
    !hasConflictingQuery && isSessionQueryValid && sessionQuery !== null
      ? sessionQuery.toLowerCase()
      : null;
  const previewDeckUuid =
    previewQuery !== null && UUID_PATTERN.test(previewQuery) ? previewQuery.toLowerCase() : null;
  const completionSummary = readCompletionSummary(location.state);
  const practice = usePracticeSession(sessionUuid, deckUuid);
  const practiceDeck = usePracticeDeckAvailability(deckUuid);
  const isActiveSession = sessionQuery !== null;
  const pageRef = useRef<HTMLDivElement | null>(null);
  const pageScrollTopRef = useRef<number | null>(null);
  const previewTriggerRef = useRef<HTMLButtonElement | null>(null);
  const shouldShowPreview = previewDeckUuid !== null && deckQuery === null && sessionQuery === null;

  useEffect(() => {
    if (!shouldShowPreview) {
      return;
    }

    const page = pageRef.current;
    if (page === null) {
      return;
    }

    const scrollTop = pageScrollTopRef.current ?? page.scrollTop;
    const previousOverflow = page.style.overflow;
    page.style.overflow = "hidden";

    return () => {
      page.style.overflow = previousOverflow;
      page.scrollTop = scrollTop;
      pageScrollTopRef.current = null;
    };
  }, [shouldShowPreview]);

  useEffect(() => {
    if (shouldShowPreview || previewTriggerRef.current === null) {
      return;
    }

    previewTriggerRef.current.focus({ preventScroll: true });
    previewTriggerRef.current = null;
  }, [shouldShowPreview]);

  function openPreview(deckUuid: string, trigger: HTMLButtonElement): void {
    pageScrollTopRef.current = pageRef.current?.scrollTop ?? null;
    previewTriggerRef.current = trigger;
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("preview", deckUuid);
    setSearchParams(nextSearchParams);
  }

  function closePreview(): void {
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.delete("preview");
    setSearchParams(nextSearchParams, { replace: true });
  }

  useEffect(() => {
    if (
      sessionUuid === null ||
      practice.state.status !== "ready" ||
      practice.state.session.uuid !== sessionUuid ||
      !practice.state.isFinished ||
      completionSummary?.sessionUuid === sessionUuid
    ) {
      return;
    }

    const summary = createCompletionSummary(
      practice.state.session,
      practice.state.timeToCompleteSeconds,
    );
    navigate(
      { pathname: location.pathname, search: location.search },
      {
        replace: true,
        state: {
          ...(isRecord(location.state) ? location.state : {}),
          practiceCompletion: summary,
        },
      },
    );
  }, [
    completionSummary?.sessionUuid,
    location.pathname,
    location.search,
    location.state,
    navigate,
    practice.state,
    sessionUuid,
  ]);

  let content;
  if (hasConflictingQuery || !isDeckQueryValid || !isSessionQueryValid) {
    content = <InvalidPracticeLinkView />;
  } else if (sessionQuery !== null) {
    if (practice.state.status === "ready" && practice.state.session.uuid === sessionUuid) {
      const terminalSubmitError = practice.state.submitError?.error;
      const isMissingSessionAfterSubmit =
        isApiError(terminalSubmitError) &&
        (terminalSubmitError.status === 403 || terminalSubmitError.status === 404);
      content = isMissingSessionAfterSubmit ? (
        <SessionErrorView error={terminalSubmitError} onRetry={practice.retryResume} />
      ) : (
        <TrackedActivePracticeSessionView
          key={practice.state.session.uuid}
          onComplete={(summary) => {
            navigate("/practice", { replace: true, state: { practiceCompletion: summary } });
          }}
          onSessionUnavailable={practice.retryResume}
          onSubmit={practice.submit}
          state={practice.state}
        />
      );
    } else if (practice.state.status === "error" && practice.state.operation === "resume") {
      const canRestoreFinishedSession =
        completionSummary !== null &&
        completionSummary.sessionUuid === sessionUuid &&
        isApiError(practice.state.error) &&
        practice.state.error.status === 409;
      content = canRestoreFinishedSession ? (
        <PracticeCompletionView summary={completionSummary} />
      ) : (
        <SessionErrorView error={practice.state.error} onRetry={practice.retryResume} />
      );
    } else {
      content = <SessionLoadingView />;
    }
  } else if (deckUuid !== null) {
    const startResourceError =
      practice.state.status === "error" &&
      practice.state.operation === "start" &&
      isApiError(practice.state.error) &&
      (practice.state.error.status === 403 || practice.state.error.status === 404);
    const availabilityStateMatches =
      practiceDeck.state.status !== "idle" && practiceDeck.state.deckUuid === deckUuid;

    if (startResourceError) {
      content = <PracticeDeckNotFoundView />;
    } else if (!availabilityStateMatches || practiceDeck.state.status === "loading") {
      content = (
        <SessionLoadingView
          ariaLabel={messages.checkingDeck}
          message={messages.checkingDeckMessage}
        />
      );
    } else if (practiceDeck.state.status === "error") {
      const isMissingDeck =
        isApiError(practiceDeck.state.error) &&
        (practiceDeck.state.error.status === 403 || practiceDeck.state.error.status === 404);
      content = isMissingDeck ? (
        <PracticeDeckNotFoundView />
      ) : (
        <PracticeDeckLoadErrorView error={practiceDeck.state.error} onRetry={practiceDeck.retry} />
      );
    } else if (practiceDeck.state.status === "ready") {
      content = (
        <PracticeSetupView
          deckUuid={deckUuid}
          deckWordsCount={practiceDeck.state.wordsCount}
          onStarted={(session) => {
            setSearchParams({ session: session.uuid }, { replace: true });
          }}
          practice={practice}
        />
      );
    } else {
      content = (
        <SessionLoadingView
          ariaLabel={messages.checkingDeck}
          message={messages.checkingDeckMessage}
        />
      );
    }
  } else if (completionSummary !== null) {
    content = <PracticeCompletionView summary={completionSummary} />;
  } else {
    const historyStartError =
      practice.state.status === "error" && practice.state.operation === "start"
        ? practice.state.error
        : null;
    content = (
      <PracticeHistoryView
        onContinue={(historySession) => {
          setSearchParams({ session: historySession.uuid }, { replace: true });
        }}
        onPreview={openPreview}
        onRepeat={async (historySession) => {
          if (historySession.deckUuid === null) return;
          const session = await practice.start(
            historySession.deckUuid,
            historySession.promptSide,
            Math.max(historySession.requestedCount, 1),
          );
          if (session !== null) {
            setSearchParams({ session: session.uuid }, { replace: true });
          }
        }}
        startError={historyStartError}
      />
    );
  }

  return (
    <div
      className={styles.page}
      data-practice-mode={isActiveSession ? "session" : "setup"}
      data-practice-view={
        deckQuery === null && sessionQuery === null
          ? "history"
          : isActiveSession
            ? "session"
            : "setup"
      }
      ref={pageRef}
    >
      <AmbientBackground />
      {content}
      {shouldShowPreview && previewDeckUuid !== null ? (
        <CatalogDeckPreview
          deckUuid={previewDeckUuid}
          onClose={closePreview}
          returnTarget="practice"
        />
      ) : null}
    </div>
  );
}

export default PracticePage;
