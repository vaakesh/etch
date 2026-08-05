import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { isApiError } from "../../api";
import { DashboardIcon, type DashboardIconName } from "../../components/DashboardVisuals";
import {
  clampPercent,
  formatCount,
  formatDeckUpdatedAt,
  formatPercent,
  formatShortWeekday,
  formatStreak,
  formatStudyTime,
} from "../../features/home/model/home-formatters";
import {
  LIBRARY_CREATE_DECK_NAVIGATION_STATE,
  LIBRARY_PATH,
} from "../../features/library/model/library-navigation";
import {
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
} from "../../i18n";
import type {
  HomeDashboard,
  HomeDeck,
  HomeProgress,
  HomeWeeklyActivityDay,
} from "../../features/home/model/home-types";
import { useHomeDashboard } from "../../features/home/model/useHomeDashboard";
import styles from "./HomePage.module.css";

const MESSAGES = defineMessages(
  {
    errors: {
      generic: "Не удалось загрузить главную страницу. Попробуйте ещё раз.",
      forbidden: "У этой учётной записи нет доступа к данным главной страницы.",
      invalid: "Сервер вернул данные в неожиданном формате. Попробуйте обновить страницу позже.",
      network: "Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.",
      server: "Сервер временно не может подготовить данные. Попробуйте ещё раз чуть позже.",
    },
    title: "Главная",
    createDeckTitle: "Создать новую колоду в библиотеке",
    newDeck: "Новая колода",
    accuracy: "Точность колоды",
    correctAnswers: (value: string) => `Правильных ответов — ${value}`,
    noDescription: "Без описания",
    lastUpdated: (value: string) => `Последнее обновление: ${value}`,
    updated: "Обновлено",
    configurePractice: (title: string) => `Настроить тренировку по колоде «${title}»`,
    startPractice: (title: string) => `Начать тренировку по колоде «${title}»`,
    start: "Начать",
    emptyTitle: "Здесь появятся ваши колоды",
    emptyDescription: "Когда колоды будут добавлены, главная страница покажет их прогресс.",
    yourDecks: "Ваши колоды",
    allDecks: "Все колоды",
    yourProgress: "Ваш прогресс",
    total: "Всего",
    studied: "Изучено",
    weekly: "За неделю",
    accuracyMetric: "Точность",
    keepGoing: "Продолжайте!",
    streak: "Текущая серия",
    studyTime: "Время занятий",
    weeklyActivity: "Активность за неделю",
    noActivity: "Пока нет данных об активности.",
    loadingAria: "Загрузка данных главной страницы",
    loading: "Загружаем данные…",
    errorTitle: "Данные не загрузились",
    retry: "Попробовать снова",
  },
  {
    errors: {
      generic: "We couldn't load the home page. Try again.",
      forbidden: "This account does not have access to the home dashboard.",
      invalid: "The server returned unexpected data. Try refreshing the page later.",
      network: "We couldn't reach the server. Check your connection and try again.",
      server: "The server cannot prepare your dashboard right now. Try again later.",
    },
    title: "Home",
    createDeckTitle: "Create a new deck in your library",
    newDeck: "New deck",
    accuracy: "Deck accuracy",
    correctAnswers: (value: string) => `Correct answers — ${value}`,
    noDescription: "No description",
    lastUpdated: (value: string) => `Last updated: ${value}`,
    updated: "Updated",
    configurePractice: (title: string) => `Configure practice for “${title}”`,
    startPractice: (title: string) => `Start practicing “${title}”`,
    start: "Start",
    emptyTitle: "Your decks will appear here",
    emptyDescription: "Once you add decks, the home page will show their progress.",
    yourDecks: "Your decks",
    allDecks: "All decks",
    yourProgress: "Your progress",
    total: "Total",
    studied: "Studied",
    weekly: "This week",
    accuracyMetric: "Accuracy",
    keepGoing: "Keep going!",
    streak: "Current streak",
    studyTime: "Study time",
    weeklyActivity: "Weekly activity",
    noActivity: "No activity yet.",
    loadingAria: "Loading home dashboard",
    loading: "Loading data…",
    errorTitle: "Your data didn't load",
    retry: "Try again",
  },
);

function getHomeErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.generic;
  }

  if (error.status === 403) {
    return messages.errors.forbidden;
  }
  if (error.code === "INVALID_HOME_RESPONSE") {
    return messages.errors.invalid;
  }
  if (error.status === 0) {
    return messages.errors.network;
  }
  if (error.status >= 500) {
    return messages.errors.server;
  }

  return messages.errors.generic;
}

function DashboardHeader() {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <header className={styles.header}>
      <h1>{messages.title}</h1>

      <div className={styles.headerActions}>
        <Link
          aria-haspopup="dialog"
          className={styles.newDeckButton}
          state={LIBRARY_CREATE_DECK_NAVIGATION_STATE}
          title={messages.createDeckTitle}
          to={LIBRARY_PATH}
        >
          <DashboardIcon name="plus" />
          <span>{messages.newDeck}</span>
        </Link>
      </div>
    </header>
  );
}

interface DeckCardProps {
  deck: HomeDeck;
}

function getAccuracyToneClassName(accuracy: number): string {
  if (accuracy >= 91) {
    return styles.deckAccuracyPurple;
  }
  if (accuracy >= 81) {
    return styles.deckAccuracyTurquoise;
  }
  if (accuracy >= 71) {
    return styles.deckAccuracyGreen;
  }
  if (accuracy >= 61) {
    return styles.deckAccuracyYellow;
  }
  if (accuracy >= 51) {
    return styles.deckAccuracyOrange;
  }

  return styles.deckAccuracyRed;
}

function DeckCard({ deck }: DeckCardProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const accuracy = clampPercent(deck.accuracy);
  const accuracyTooltipId = useId();
  const [isAccuracyTooltipOpen, setIsAccuracyTooltipOpen] = useState(false);
  const updatedAtLabel = formatDeckUpdatedAt(deck.updatedAt, locale);
  const wordCount = localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale);
  const accuracyHintClassName = isAccuracyTooltipOpen
    ? `${styles.deckAccuracyHint} ${styles.deckAccuracyHintOpen}`
    : styles.deckAccuracyHint;

  return (
    <article className={styles.deckCard}>
      <div className={styles.deckCopy}>
        <div className={styles.deckHeading}>
          <h3>{deck.title}</h3>
          <span className={accuracyHintClassName}>
            <span
              aria-describedby={accuracyTooltipId}
              aria-label={messages.accuracy}
              aria-valuemax={100}
              aria-valuemin={0}
              aria-valuenow={accuracy}
              aria-valuetext={formatPercent(accuracy, locale)}
              className={`${styles.deckAccuracy} ${getAccuracyToneClassName(accuracy)}`}
              onBlur={() => setIsAccuracyTooltipOpen(false)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setIsAccuracyTooltipOpen(false);
                  event.currentTarget.blur();
                } else if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setIsAccuracyTooltipOpen((isOpen) => !isOpen);
                }
              }}
              onPointerDown={(event) => {
                if (event.button === 0) {
                  setIsAccuracyTooltipOpen((isOpen) => !isOpen);
                }
              }}
              role="meter"
              tabIndex={0}
            >
              {formatCount(accuracy, locale)}
            </span>
            <span className={styles.deckAccuracyTooltip} id={accuracyTooltipId} role="tooltip">
              <strong>{messages.accuracy}</strong>
              <span>{messages.correctAnswers(formatPercent(accuracy, locale))}</span>
            </span>
          </span>
        </div>
        <p>{deck.description ?? messages.noDescription}</p>
      </div>

      <div className={styles.deckBody}>
        <div className={styles.deckStats}>
          <p>
            <strong>{wordCount.formattedValue}</strong> {wordCount.unit}
          </p>
          {deck.updatedAt !== null && updatedAtLabel !== null ? (
            <time
              className={styles.deckUpdatedAt}
              dateTime={deck.updatedAt}
              title={messages.lastUpdated(updatedAtLabel)}
            >
              <span className={styles.deckUpdatedLabel}>{messages.updated}</span>
              <span className={styles.deckUpdatedValue}>{updatedAtLabel}</span>
            </time>
          ) : null}
        </div>
      </div>

      <Link
        aria-label={messages.configurePractice(deck.title)}
        className={styles.startButton}
        title={messages.startPractice(deck.title)}
        to={`/practice?deck=${encodeURIComponent(deck.uuid)}`}
      >
        {messages.start}
      </Link>
    </article>
  );
}

function EmptyDecks() {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div className={styles.emptyDecks}>
      <div aria-hidden="true" className={styles.emptyIllustration}>
        <span />
        <span />
        <span>
          <DashboardIcon name="book" />
        </span>
      </div>
      <div>
        <h3>{messages.emptyTitle}</h3>
        <p>{messages.emptyDescription}</p>
      </div>
    </div>
  );
}

function DecksSection({ decks }: { decks: readonly HomeDeck[] }) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <section aria-labelledby="decks-heading" className={styles.decksSection}>
      <div className={styles.sectionHeading}>
        <h2 id="decks-heading">{messages.yourDecks}</h2>
        {decks.length > 0 ? (
          <Link className={styles.sectionAction} to="/library">
            {messages.allDecks}
            <DashboardIcon name="chevron" />
          </Link>
        ) : null}
      </div>

      {decks.length > 0 ? (
        <div className={styles.decksGrid}>
          {decks.map((deck) => (
            <DeckCard deck={deck} key={deck.uuid} />
          ))}
        </div>
      ) : (
        <EmptyDecks />
      )}
    </section>
  );
}

interface ProgressMetricProps {
  icon: DashboardIconName;
  label: string;
  value: string;
  detail: string;
  tone: "teal" | "mint" | "coral" | "sand";
}

function ProgressMetric({ icon, label, value, detail, tone }: ProgressMetricProps) {
  return (
    <div className={styles.progressMetric}>
      <div className={`${styles.metricIcon} ${styles[`metricIcon${tone}`]}`}>
        <DashboardIcon name={icon} />
      </div>
      <div className={styles.metricCopy}>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}

interface ProgressPanelProps {
  progress: HomeProgress;
  weeklyActivity: readonly HomeWeeklyActivityDay[];
}

function ProgressPanel({ progress, weeklyActivity }: ProgressPanelProps) {
  const { locale } = useLocale();
  const messages = useLocalizedMessages(MESSAGES);
  const chartValues = [...weeklyActivity]
    .sort((first, second) => first.date.localeCompare(second.date))
    .slice(-7);
  const studiedWordsCount = localizeCount(progress.wordsExplored, WORD_COUNT_FORMS, locale);

  return (
    <aside aria-labelledby="progress-heading" className={styles.progressPanel}>
      <header className={styles.progressHeading}>
        <span aria-hidden="true" className={styles.progressHeadingIcon}>
          <DashboardIcon name="chart" />
        </span>
        <h2 id="progress-heading">{messages.yourProgress}</h2>
      </header>

      <div className={styles.metricsList}>
        <ProgressMetric
          detail={messages.total}
          icon="book"
          label={messages.studied}
          tone="teal"
          value={studiedWordsCount.text}
        />
        <ProgressMetric
          detail={messages.weekly}
          icon="gauge"
          label={messages.accuracyMetric}
          tone="mint"
          value={formatPercent(progress.weeklyAccuracy, locale)}
        />
        <ProgressMetric
          detail={messages.keepGoing}
          icon="calendar"
          label={messages.streak}
          tone="coral"
          value={formatStreak(progress.currentStreakDays, locale)}
        />
        <ProgressMetric
          detail={messages.total}
          icon="clock"
          label={messages.studyTime}
          tone="sand"
          value={formatStudyTime(progress.totalStudyTimeSeconds, locale)}
        />
      </div>

      <section aria-labelledby="weekly-heading" className={styles.weeklySection}>
        <h3 id="weekly-heading">{messages.weeklyActivity}</h3>
        {chartValues.length > 0 ? (
          <div className={styles.weeklyChart}>
            {chartValues.map((activityDay) => {
              const percent = clampPercent(activityDay.percent);
              const weekday = formatShortWeekday(activityDay.date, locale);

              return (
                <div className={styles.weeklyBar} key={activityDay.date}>
                  <div className={styles.barTrack}>
                    <span
                      aria-label={`${weekday}, ${activityDay.date}: ${formatPercent(percent, locale)}`}
                      className={styles.barFill}
                      role="img"
                      style={{ height: `${Math.max(4, percent)}%` }}
                    />
                  </div>
                  <span>{weekday}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className={styles.noActivity}>{messages.noActivity}</p>
        )}
      </section>
    </aside>
  );
}

function DashboardContent({ dashboard }: { dashboard: HomeDashboard }) {
  return (
    <div className={styles.contentGrid}>
      <ProgressPanel progress={dashboard.progress} weeklyActivity={dashboard.weeklyActivity} />
      <div className={styles.mainColumn}>
        <DecksSection decks={dashboard.decks} />
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div aria-label={messages.loadingAria} className={styles.contentGrid} role="status">
      <span className={styles.srOnly}>{messages.loading}</span>
      <aside className={styles.skeletonPanel}>
        <span className={styles.skeletonLineWide} />
        <div className={styles.skeletonMetrics}>
          {Array.from({ length: 4 }, (_, index) => (
            <span className={styles.skeletonMetric} key={index} />
          ))}
        </div>
        <span className={styles.skeletonChart} />
      </aside>
      <div className={styles.mainColumn}>
        <section className={styles.decksSection}>
          <div className={styles.skeletonHeading} />
          <div className={styles.decksGrid}>
            {Array.from({ length: 3 }, (_, index) => (
              <div className={styles.skeletonCard} key={index}>
                <span className={styles.skeletonLineWide} />
                <span className={styles.skeletonLine} />
                <span className={styles.skeletonArtwork} />
                <span className={styles.skeletonButton} />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

interface ErrorStateProps {
  error: unknown;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <section className={styles.errorState}>
      <div className={styles.errorIcon}>
        <DashboardIcon name="book" />
      </div>
      <h2>{messages.errorTitle}</h2>
      <p>{getHomeErrorMessage(error, messages)}</p>
      <button onClick={onRetry} type="button">
        {messages.retry}
      </button>
    </section>
  );
}

export function HomePage() {
  const { data, error, retry, status } = useHomeDashboard();

  return (
    <main className={styles.page}>
      <section className={styles.dashboard}>
        <DashboardHeader />
        {status === "loading" ? <DashboardSkeleton /> : null}
        {status === "error" && error !== null ? <ErrorState error={error} onRetry={retry} /> : null}
        {status === "success" && data !== null ? <DashboardContent dashboard={data} /> : null}
      </section>
    </main>
  );
}

export default HomePage;
