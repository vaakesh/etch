import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { isApiError } from "../../api";
import { DashboardIcon } from "../../components/DashboardVisuals";
import type { CardSide } from "../../features/practice/model/practice-types";
import { formatNextReview } from "../../features/reviews/model/review-formatters";
import type {
  ActiveReviewSession,
  ReviewSideSummary,
  ReviewSummary,
} from "../../features/reviews/model/review-types";
import { useReviewToday, type ReviewStartState } from "../../features/reviews/model/useReviewToday";
import {
  WORD_COUNT_FORMS,
  defineMessages,
  formatNumber,
  localizeCount,
  useLocale,
  useLocalizedMessages,
} from "../../i18n";
import styles from "./ReviewTodayPanel.module.css";

const MESSAGES = defineMessages(
  {
    title: "Повторить сегодня",
    lead: "Слова, которые пора освежить, пока они не забылись",
    translation: "Перевод",
    word: "Слово",
    translationLower: "перевод",
    wordLower: "слово",
    direction: (from: string, to: string) => `${from} → ${to}`,
    toReview: "к повторению",
    review: "Повторить",
    starting: "Готовим…",
    reviewAria: (count: string, direction: string) => `Повторить ${count}: ${direction}`,
    restartHint: "Незаконченное повторение будет закрыто",
    allDone: "На сегодня всё",
    nextReview: "Следующее повторение",
    nothingScheduled: "Новых повторений пока нет",
    emptyTitle: "Пока нечего повторять",
    emptyDescription:
      "Слова появятся здесь после первых тренировок — мы подскажем, когда их пора освежить.",
    continueTitle: "Незаконченное повторение",
    continueAction: "Продолжить",
    continueProgress: (answered: string, total: string) => `${answered} из ${total}`,
    continueAria: (answered: string, total: string) =>
      `Продолжить повторение: отвечено ${answered} из ${total}`,
    loadingAria: "Загрузка слов для повторения",
    loadError: "Не удалось загрузить слова для повторения.",
    retry: "Попробовать снова",
    startErrors: {
      noCards: "Слова на сегодня уже повторены — список обновлён.",
      alreadyStarted: "Повторение уже началось в другой вкладке — список обновлён.",
      network: "Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.",
      generic: "Не удалось начать повторение. Попробуйте ещё раз.",
    },
  },
  {
    title: "Review today",
    lead: "Words worth refreshing before they fade",
    translation: "Translation",
    word: "Word",
    translationLower: "translation",
    wordLower: "word",
    direction: (from: string, to: string) => `${from} → ${to}`,
    toReview: "to review",
    review: "Review",
    starting: "Preparing…",
    reviewAria: (count: string, direction: string) => `Review ${count}: ${direction}`,
    restartHint: "Your unfinished review will be closed",
    allDone: "All done for today",
    nextReview: "Next review",
    nothingScheduled: "No reviews scheduled yet",
    emptyTitle: "Nothing to review yet",
    emptyDescription:
      "Words will show up here after your first practice — we'll tell you when they need a refresh.",
    continueTitle: "Unfinished review",
    continueAction: "Continue",
    continueProgress: (answered: string, total: string) => `${answered} of ${total}`,
    continueAria: (answered: string, total: string) =>
      `Continue review: ${answered} of ${total} answered`,
    loadingAria: "Loading words to review",
    loadError: "We couldn't load your words to review.",
    retry: "Try again",
    startErrors: {
      noCards: "Today's words are already reviewed — the list has been refreshed.",
      alreadyStarted: "A review already started in another tab — the list has been refreshed.",
      network: "We couldn't reach the server. Check your connection and try again.",
      generic: "We couldn't start the review. Try again.",
    },
  },
);

type Messages = (typeof MESSAGES)["ru-RU"];

const SIDES: readonly CardSide[] = ["front", "back"];

function getDirectionParts(side: CardSide, messages: Messages): readonly [string, string] {
  // front-подсказка — перевод, ответ — слово; как в настройке тренировки
  return side === "front"
    ? [messages.translation, messages.wordLower]
    : [messages.word, messages.translationLower];
}

function getStartErrorMessage(error: unknown, messages: Messages): string {
  if (!isApiError(error)) {
    return messages.startErrors.generic;
  }
  if (error.code === "NO_CARDS_TO_REVIEW") {
    return messages.startErrors.noCards;
  }
  if (error.code === "TRAINING_SESSION_ALREADY_EXISTS") {
    return messages.startErrors.alreadyStarted;
  }
  if (error.code === "NETWORK_ERROR") {
    return messages.startErrors.network;
  }
  return messages.startErrors.generic;
}

function isSummaryEmpty(summary: ReviewSummary): boolean {
  return (
    summary.activeSession === null &&
    SIDES.every(
      (side) => summary.sides[side].dueToday === 0 && summary.sides[side].nextDueAt === null,
    )
  );
}

function ArrowIcon() {
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
      <path d="M5 12h14m-6-6 6 6-6 6" />
    </svg>
  );
}

interface ContinueLinkProps {
  session: ActiveReviewSession;
}

function ContinueLink({ session }: ContinueLinkProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const answered = formatNumber(session.answeredCount, locale);
  const total = formatNumber(session.totalCount, locale);
  const progress = Math.round((session.answeredCount / session.totalCount) * 100);

  return (
    <Link
      aria-label={messages.continueAria(answered, total)}
      className={styles.continueLink}
      to={`/practice?session=${encodeURIComponent(session.uuid)}`}
    >
      <span className={styles.continueCopy}>
        <span className={styles.continueTitle}>{messages.continueTitle}</span>
        <span className={styles.continueProgress}>
          <span aria-hidden="true" className={styles.continueTrack}>
            <span style={{ width: `${progress}%` }} />
          </span>
          {messages.continueProgress(answered, total)}
        </span>
      </span>
      <span className={styles.continueAction}>
        {messages.continueAction}
        <ArrowIcon />
      </span>
    </Link>
  );
}

interface SideCardProps {
  side: CardSide;
  summary: ReviewSideSummary;
  now: Date;
  hasActiveSession: boolean;
  startState: ReviewStartState;
  onStart: (side: CardSide) => void;
}

function SideCard({ side, summary, now, hasActiveSession, startState, onStart }: SideCardProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const [from, to] = getDirectionParts(side, messages);
  const direction = messages.direction(from, to);
  const dueToday = localizeCount(summary.dueToday, WORD_COUNT_FORMS, locale);
  const isStarting = startState.status === "starting" && startState.side === side;
  const isBusy = startState.status === "starting";
  const nextReview =
    summary.nextDueAt === null ? null : formatNextReview(summary.nextDueAt, now, locale);
  const hasDueWords = summary.dueToday > 0;

  return (
    <article className={styles.sideCard} data-due={hasDueWords}>
      <div className={styles.sideTop}>
        <h3 aria-label={direction} className={styles.direction}>
          <span>{from}</span>
          <ArrowIcon />
          <span>{to}</span>
        </h3>
      </div>

      {hasDueWords ? (
        <>
          <p className={styles.sideCount}>
            <strong>{dueToday.formattedValue}</strong>
            <span>
              {dueToday.unit} {messages.toReview}
            </span>
          </p>
          <button
            aria-label={
              isStarting ? messages.starting : messages.reviewAria(dueToday.text, direction)
            }
            className={styles.reviewButton}
            disabled={isBusy}
            onClick={() => onStart(side)}
            title={hasActiveSession ? messages.restartHint : undefined}
            type="button"
          >
            <span>{isStarting ? messages.starting : messages.review}</span>
            <ArrowIcon />
          </button>
        </>
      ) : (
        <>
          <p className={styles.sideDone}>
            <span aria-hidden="true" className={styles.sideDoneIcon}>
              <DashboardIcon name="calendar" />
            </span>
            <strong>{messages.allDone}</strong>
          </p>
          <p className={styles.nextReview}>
            <DashboardIcon name="clock" />
            {nextReview !== null && summary.nextDueAt !== null ? (
              <span>
                {messages.nextReview} <time dateTime={summary.nextDueAt}>{nextReview}</time>
              </span>
            ) : (
              <span>{messages.nothingScheduled}</span>
            )}
          </p>
        </>
      )}
    </article>
  );
}

function PanelSkeleton() {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div aria-label={messages.loadingAria} className={styles.sides} role="status">
      {SIDES.map((side) => (
        <div className={styles.skeletonCard} key={side}>
          <span className={styles.skeletonLine} />
          <span className={styles.skeletonCount} />
          <span className={styles.skeletonButton} />
        </div>
      ))}
    </div>
  );
}

export function ReviewTodayPanel() {
  const messages = useLocalizedMessages(MESSAGES);
  const navigate = useNavigate();
  const { summary, startState, retry, start } = useReviewToday();
  // Момент открытия страницы: от него считается «через N часов» до следующего повторения
  const [now] = useState(() => new Date());

  async function handleStart(side: CardSide): Promise<void> {
    const session = await start(side);
    if (session !== null) {
      navigate(`/practice?session=${encodeURIComponent(session.uuid)}`);
    }
  }

  let body;
  if (summary.status === "loading") {
    body = <PanelSkeleton />;
  } else if (summary.status === "error") {
    body = (
      <div className={styles.loadError} role="alert">
        <p>{messages.loadError}</p>
        <button className={styles.retryButton} onClick={retry} type="button">
          {messages.retry}
        </button>
      </div>
    );
  } else if (isSummaryEmpty(summary.data)) {
    body = (
      <div className={styles.emptyState}>
        <span aria-hidden="true" className={styles.emptyIcon}>
          <DashboardIcon name="book" />
        </span>
        <div>
          <h3>{messages.emptyTitle}</h3>
          <p>{messages.emptyDescription}</p>
        </div>
      </div>
    );
  } else {
    const data = summary.data;
    body = (
      <div className={styles.sides}>
        {SIDES.map((side) => (
          <SideCard
            hasActiveSession={data.activeSession !== null}
            key={side}
            now={now}
            onStart={(nextSide) => void handleStart(nextSide)}
            side={side}
            startState={startState}
            summary={data.sides[side]}
          />
        ))}
      </div>
    );
  }

  const activeSession = summary.status === "success" ? summary.data.activeSession : null;

  return (
    <section aria-labelledby="review-heading" className={styles.reviewPanel}>
      <header className={styles.reviewHeader}>
        <div className={styles.reviewHeading}>
          <span aria-hidden="true" className={styles.reviewHeadingIcon}>
            <DashboardIcon name="calendar" />
          </span>
          <div>
            <h2 id="review-heading">{messages.title}</h2>
            <p>{messages.lead}</p>
          </div>
        </div>
        {activeSession !== null ? <ContinueLink session={activeSession} /> : null}
      </header>

      {body}

      {startState.status === "error" ? (
        <p className={styles.startError} role="alert">
          {getStartErrorMessage(startState.error, messages)}
        </p>
      ) : null}
    </section>
  );
}
