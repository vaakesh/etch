import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { isApiError } from "../../api";
import { getPracticePaginationTokens } from "../../features/practice/model/practice-pagination";
import type {
  CardSide,
  PracticeCard,
  PracticeSession,
} from "../../features/practice/model/practice-types";
import {
  usePracticeSession,
  type PracticeCardFeedback,
  type ReadyPracticeState,
  type UsePracticeSessionResult,
} from "../../features/practice/model/usePracticeSession";
import {
  CORRECT_ANSWER_COUNT_FORMS,
  MINUTE_SHORT_COUNT_FORMS,
  SECOND_SHORT_COUNT_FORMS,
  WRONG_ANSWER_COUNT_FORMS,
  formatNumber,
  localizeCount,
  useLocale,
  type AppLocale,
} from "../../i18n";
import styles from "./PracticePage.module.css";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function ArrowIcon({ direction = "right" }: { direction?: "left" | "right" }) {
  return (
    <svg
      aria-hidden="true"
      className={direction === "left" ? styles.iconReversed : undefined}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M5 12h14M14 7l5 5-5 5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="m6 6 12 12M18 6 6 18" />
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

function PracticeHeader({ compact = false }: { compact?: boolean }) {
  return (
    <header className={compact ? `${styles.header} ${styles.headerCompact}` : styles.header}>
      <Link aria-label="На главную" className={styles.brand} to="/">
        <ArrowIcon direction="left" />
      </Link>

      <div className={styles.headerMode}>
        <span>Практика</span>
      </div>

      <Link
        aria-label="Выйти из практики в библиотеку"
        className={styles.closeButton}
        to="/library"
      >
        <span>В библиотеку</span>
        <CloseIcon />
      </Link>
    </header>
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

function getPracticeErrorMessage(error: unknown, operation: "resume" | "start" | "submit"): string {
  if (!isApiError(error)) {
    return "Что-то пошло не так. Попробуйте ещё раз.";
  }

  if (error.code === "INVALID_PRACTICE_RESPONSE") {
    return "Сервер вернул данные тренировки в неожиданном формате.";
  }
  if (error.status === 403) {
    return "У вас нет доступа к этой колоде.";
  }
  if (error.status === 404) {
    return operation === "start"
      ? "Колода не найдена или больше недоступна."
      : "Тренировочная сессия не найдена или больше недоступна.";
  }
  if (error.status === 409) {
    if (operation === "start") {
      return "В этой колоде пока нет карточек для тренировки.";
    }
    return operation === "resume"
      ? "Эта тренировочная сессия уже завершена."
      : "Сессия уже завершена — этот ответ отправить нельзя.";
  }
  if (error.status === 422) {
    return operation === "submit"
      ? "Ответ не прошёл проверку. Проверьте текст и попробуйте снова."
      : "Ссылка на тренировку содержит некорректные данные.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может продолжить тренировку.";
  }

  return "Не удалось продолжить тренировку. Попробуйте ещё раз.";
}

function LandingView() {
  return (
    <main className={styles.centeredMain}>
      <section className={`${styles.paperPanel} ${styles.landingPanel}`}>
        <div aria-hidden="true" className={styles.deckPreview}>
          <span />
          <span />
          <span />
        </div>
        <h1>Сначала выберите колоду</h1>
        <p>Откройте библиотеку и выберите колоду.</p>
        <Link className={styles.primaryAction} to="/library">
          Выбрать колоду
          <ArrowIcon />
        </Link>
      </section>
    </main>
  );
}

interface SetupViewProps {
  deckUuid: string;
  practice: UsePracticeSessionResult;
  onStarted: (session: PracticeSession) => void;
}

export function PracticeSetupView({ deckUuid, onStarted, practice }: SetupViewProps) {
  const [promptSide, setPromptSide] = useState<CardSide>("front");
  const promptSideHintId = useId();
  const isStarting = practice.state.status === "loading" && practice.state.operation === "start";
  const startError =
    practice.state.status === "error" && practice.state.operation === "start"
      ? practice.state.error
      : null;

  const handleStart = async () => {
    const session = await practice.start(deckUuid, promptSide);
    if (session !== null) {
      onStarted(session);
    }
  };

  return (
    <main className={styles.centeredMain}>
      <section aria-busy={isStarting} className={styles.setupPanel}>
        <div className={styles.setupHeading}>
          <div aria-hidden="true" className={styles.setupLetters}>
            <span>A</span>
            <span>B</span>
          </div>
          <h1>Как будем тренироваться?</h1>
        </div>

        <div className={styles.setupControls}>
          <fieldset
            aria-describedby={promptSideHintId}
            className={styles.optionGroup}
            disabled={isStarting}
          >
            <legend>Что показывать сначала?</legend>
            <div className={styles.sideOptions}>
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
                <span className={styles.optionCopy}>
                  <strong>Слово → перевод</strong>
                  <small>Показываем исходное слово — вы вводите перевод</small>
                </span>
                <span aria-hidden="true" className={styles.optionCheck} />
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
                <span className={styles.optionCopy}>
                  <strong>Перевод → слово</strong>
                  <small>Показываем перевод — вы вводите исходное слово</small>
                </span>
                <span aria-hidden="true" className={styles.optionCheck} />
              </label>
            </div>
            <p className={styles.visuallyHidden} id={promptSideHintId}>
              Направление можно будет изменить перед следующей сессией.
            </p>
          </fieldset>

          <div aria-label="Количество карточек" className={styles.sessionScope}>
            <span>Объём</span>
            <strong>Вся колода</strong>
          </div>

          {startError === null ? null : (
            <p className={styles.inlineError} role="alert">
              {getPracticeErrorMessage(startError, "start")}
            </p>
          )}

          <div className={styles.setupFooter}>
            <Link className={styles.secondaryAction} to="/library">
              Назад
            </Link>
            <button
              className={styles.primaryAction}
              disabled={isStarting}
              onClick={() => void handleStart()}
              type="button"
            >
              {isStarting ? <span className={styles.buttonSpinner} /> : null}
              {isStarting ? "Готовим…" : "Начать"}
              {isStarting ? null : <ArrowIcon />}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

function SessionLoadingView() {
  return (
    <main className={styles.sessionMain}>
      <div
        aria-label="Загружаем тренировочную сессию"
        className={styles.sessionLoader}
        role="status"
      >
        <span className={styles.loaderCore} />
        <p>Загружаем…</p>
      </div>
    </main>
  );
}

function SessionErrorView({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const isFinishedSession = isApiError(error) && error.status === 409;

  return (
    <main className={styles.centeredMain}>
      <section className={`${styles.paperPanel} ${styles.errorPanel}`} role="alert">
        <h1>Не получилось продолжить</h1>
        <p>{getPracticeErrorMessage(error, "resume")}</p>
        <div className={styles.errorActions}>
          {isFinishedSession ? null : (
            <button className={styles.primaryAction} onClick={onRetry} type="button">
              Попробовать снова
            </button>
          )}
          <Link className={styles.secondaryAction} to="/library">
            {isFinishedSession ? "Выбрать новую тренировку" : "В библиотеку"}
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
  deckUuid: string;
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
    typeof deckUuid !== "string" ||
    !UUID_PATTERN.test(deckUuid) ||
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
    deckUuid: deckUuid.toLowerCase(),
    sessionUuid: sessionUuid.toLowerCase(),
    timeToCompleteSeconds,
    totalCount,
    wrongCount,
  };
}

export function PracticeCompletionView({ summary }: CompletionViewProps) {
  const { locale } = useLocale();
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
        <h1>Колода пройдена</h1>

        <dl className={styles.completionStats}>
          <div>
            <dt>Верно</dt>
            <dd>{summary.correctCount}</dd>
          </div>
          <div>
            <dt>Ошибки</dt>
            <dd>{summary.wrongCount}</dd>
          </div>
          <div>
            <dt>Время</dt>
            <dd>{formatDuration(summary.timeToCompleteSeconds, locale)}</dd>
          </div>
        </dl>

        <div className={styles.completionActions}>
          <Link className={styles.primaryAction} to={`/practice?deck=${summary.deckUuid}`}>
            Ещё раз
            <ArrowIcon />
          </Link>
          <Link className={styles.secondaryAction} to="/library">
            В библиотеку
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
        aria-label={`Отвечено ${session.answeredCount} из ${session.totalCount}`}
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
  const sequenceNumbers = cards.map((card) => card.sequenceNumber);
  const tokens = getPracticePaginationTokens(sequenceNumbers, currentSequenceNumber, locale);
  const currentIndex = sequenceNumbers.indexOf(currentSequenceNumber);
  const previousSequenceNumber = currentIndex > 0 ? sequenceNumbers[currentIndex - 1] : undefined;
  const nextSequenceNumber =
    currentIndex >= 0 && currentIndex < sequenceNumbers.length - 1
      ? sequenceNumbers[currentIndex + 1]
      : undefined;

  return (
    <nav aria-label="Карточки сессии" className={styles.pagination}>
      <button
        aria-label="Предыдущая карточка"
        className={styles.paginationArrow}
        disabled={isDisabled || previousSequenceNumber === undefined}
        onClick={() => previousSequenceNumber !== undefined && onSelect(previousSequenceNumber)}
        type="button"
      >
        <ArrowIcon direction="left" />
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
              aria-label={token.ariaLabel}
              className={className}
              disabled={isDisabled}
              key={token.key}
              onClick={() => onSelect(token.sequenceNumber)}
              type="button"
            >
              {token.label}
              {feedback === undefined ? null : (
                <span className={styles.pageNumberStatus}>
                  <ResultIcon isCorrect={feedback.isCorrect} />
                </span>
              )}
            </button>
          );
        })}
      </div>

      <button
        aria-label="Следующая карточка"
        className={styles.paginationArrow}
        disabled={isDisabled || nextSequenceNumber === undefined}
        onClick={() => nextSequenceNumber !== undefined && onSelect(nextSequenceNumber)}
        type="button"
      >
        <ArrowIcon />
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
  const inputId = useId();
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

  const liveMessage =
    feedback === undefined
      ? submitError === null
        ? ""
        : getPracticeErrorMessage(submitError, "submit")
      : feedback.isCorrect
        ? `Ответ верный. Правильный ответ: ${feedback.answerText}`
        : `Ответ неверный. Правильный ответ: ${feedback.answerText}`;

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
            <strong>{feedback.isCorrect ? "Верно" : "Не совсем"}</strong>
            <span>
              {feedback.isCorrect
                ? feedback.answerText
                : `Правильный ответ: ${feedback.answerText}`}
            </span>
          </div>
          <button
            className={styles.continueButton}
            onClick={isFinished || nextSequenceNumber === null ? onFinish : onContinue}
            ref={continueButtonRef}
            type="button"
          >
            {isFinished || nextSequenceNumber === null ? "Результат" : "Дальше"}
            <ArrowIcon />
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
        <label className={styles.visuallyHidden} htmlFor={inputId}>
          Ваш ответ
        </label>
        <div className={styles.answerControls}>
          <input
            autoComplete="off"
            autoFocus
            disabled={isSubmitting}
            id={inputId}
            lang={card.answerLanguage}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Ваш ответ"
            type="text"
            value={value}
          />
          <button
            aria-label="Отправить ответ"
            className={styles.submitButton}
            disabled={isSubmitting || !value.trim()}
            type="submit"
          >
            {isSubmitting ? <span className={styles.buttonSpinner} /> : <ArrowIcon />}
          </button>
        </div>
        <div className={styles.answerMeta}>
          <button disabled={isSubmitting} onClick={onSkip} type="button">
            Не знаю
          </button>
        </div>
        {submitError === null ? null : (
          <p className={styles.submitError}>{getPracticeErrorMessage(submitError, "submit")}</p>
        )}
      </form>
    </div>
  );
}

interface ActiveSessionViewProps {
  state: ReadyPracticeState;
  onSubmit: UsePracticeSessionResult["submit"];
  onComplete: (summary: PracticeCompletionSummary) => void;
}

export function ActivePracticeSessionView({ onComplete, onSubmit, state }: ActiveSessionViewProps) {
  const { locale } = useLocale();
  const [selectedSequenceNumber, setSelectedSequenceNumber] = useState(
    state.session.cards[0]?.sequenceNumber ?? 1,
  );
  const [draftsBySequence, setDraftsBySequence] = useState<Readonly<Record<number, string>>>({});

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
    <main className={styles.sessionMain}>
      <SessionProgress session={state.session} />

      <section aria-labelledby="practice-prompt" className={styles.cardStage}>
        <article className={cardClassName} key={selectedCard.sequenceNumber}>
          <div className={styles.cardTopline}>
            <span
              aria-label={`Карточка ${selectedCard.sequenceNumber}`}
              className={styles.cardNumber}
            >
              {String(selectedCard.sequenceNumber).padStart(2, "0")}
            </span>
            <span
              aria-label={`Язык вопроса ${selectedCard.promptLanguage}, язык ответа ${selectedCard.answerLanguage}`}
              className={styles.languageFlow}
            >
              <span>{formatLanguage(selectedCard.promptLanguage, locale)}</span>
              <ArrowIcon />
              <span>{formatLanguage(selectedCard.answerLanguage, locale)}</span>
            </span>
          </div>

          <div className={styles.promptArea}>
            <h1 id="practice-prompt" lang={selectedCard.promptLanguage}>
              {selectedCard.promptText}
            </h1>
          </div>

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
    </main>
  );
}

function InvalidPracticeLinkView() {
  return (
    <main className={styles.centeredMain}>
      <section className={`${styles.paperPanel} ${styles.errorPanel}`} role="alert">
        <h1>Некорректная ссылка</h1>
        <p>Выберите колоду заново — так мы точно запустим правильную тренировку.</p>
        <Link className={styles.primaryAction} to="/library">
          Перейти в библиотеку
        </Link>
      </section>
    </main>
  );
}

export function PracticePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const deckQuery = searchParams.get("deck");
  const sessionQuery = searchParams.get("session");
  const hasConflictingQuery = deckQuery !== null && sessionQuery !== null;
  const isDeckQueryValid = deckQuery === null || UUID_PATTERN.test(deckQuery);
  const isSessionQueryValid = sessionQuery === null || UUID_PATTERN.test(sessionQuery);
  const deckUuid =
    !hasConflictingQuery && isDeckQueryValid && deckQuery !== null ? deckQuery.toLowerCase() : null;
  const sessionUuid =
    !hasConflictingQuery && isSessionQueryValid && sessionQuery !== null
      ? sessionQuery.toLowerCase()
      : null;
  const completionSummary = readCompletionSummary(location.state);
  const practice = usePracticeSession(sessionUuid, deckUuid);
  const isActiveSession = sessionQuery !== null;

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
      content = (
        <ActivePracticeSessionView
          key={practice.state.session.uuid}
          onComplete={(summary) => {
            navigate("/practice", { replace: true, state: { practiceCompletion: summary } });
          }}
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
    content = (
      <PracticeSetupView
        deckUuid={deckUuid}
        onStarted={(session) => {
          setSearchParams({ session: session.uuid }, { replace: true });
        }}
        practice={practice}
      />
    );
  } else if (completionSummary !== null) {
    content = <PracticeCompletionView summary={completionSummary} />;
  } else {
    content = <LandingView />;
  }

  return (
    <div className={styles.page} data-practice-mode={isActiveSession ? "session" : "setup"}>
      <AmbientBackground />
      <PracticeHeader compact={isActiveSession} />
      {content}
    </div>
  );
}

export default PracticePage;
