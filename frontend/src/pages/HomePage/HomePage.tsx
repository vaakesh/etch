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
import { WORD_COUNT_FORMS, localizeCount, useLocale } from "../../i18n";
import type {
  HomeDashboard,
  HomeDeck,
  HomeProgress,
  HomeWeeklyActivityDay,
} from "../../features/home/model/home-types";
import { useHomeDashboard } from "../../features/home/model/useHomeDashboard";
import styles from "./HomePage.module.css";

function getHomeErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось загрузить главную страницу. Попробуйте ещё раз.";
  }

  if (error.status === 403) {
    return "У этой учётной записи нет доступа к данным главной страницы.";
  }
  if (error.code === "INVALID_HOME_RESPONSE") {
    return "Сервер вернул данные в неожиданном формате. Попробуйте обновить страницу позже.";
  }
  if (error.status === 0) {
    return "Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.";
  }
  if (error.status >= 500) {
    return "Сервер временно не может подготовить данные. Попробуйте ещё раз чуть позже.";
  }

  return "Не удалось загрузить главную страницу. Попробуйте ещё раз.";
}

function DashboardHeader() {
  return (
    <header className={styles.header}>
      <h1>Главная</h1>

      <div className={styles.headerActions}>
        <Link
          aria-haspopup="dialog"
          className={styles.newDeckButton}
          state={LIBRARY_CREATE_DECK_NAVIGATION_STATE}
          title="Создать новую колоду в библиотеке"
          to={LIBRARY_PATH}
        >
          <DashboardIcon name="plus" />
          <span>Новая колода</span>
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
              aria-label="Точность колоды"
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
              <strong>Точность колоды</strong>
              <span>Правильных ответов — {formatPercent(accuracy, locale)}</span>
            </span>
          </span>
        </div>
        <p>{deck.description ?? "Без описания"}</p>
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
              title={`Последнее обновление: ${updatedAtLabel}`}
            >
              <span className={styles.deckUpdatedLabel}>Обновлено</span>
              <span className={styles.deckUpdatedValue}>{updatedAtLabel}</span>
            </time>
          ) : null}
        </div>
      </div>

      <Link
        aria-label={`Настроить тренировку по колоде «${deck.title}»`}
        className={styles.startButton}
        title={`Начать тренировку по колоде «${deck.title}»`}
        to={`/practice?deck=${encodeURIComponent(deck.uuid)}`}
      >
        Начать
      </Link>
    </article>
  );
}

function EmptyDecks() {
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
        <h3>Здесь появятся ваши колоды</h3>
        <p>Когда колоды будут добавлены, главная страница покажет их прогресс.</p>
      </div>
    </div>
  );
}

function DecksSection({ decks }: { decks: readonly HomeDeck[] }) {
  return (
    <section aria-labelledby="decks-heading" className={styles.decksSection}>
      <div className={styles.sectionHeading}>
        <h2 id="decks-heading">Ваши колоды</h2>
        {decks.length > 0 ? (
          <Link className={styles.sectionAction} to="/library">
            Все колоды
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
        <h2 id="progress-heading">Ваш прогресс</h2>
      </header>

      <div className={styles.metricsList}>
        <ProgressMetric
          detail="Всего"
          icon="book"
          label="Изучено"
          tone="teal"
          value={studiedWordsCount.text}
        />
        <ProgressMetric
          detail="За неделю"
          icon="gauge"
          label="Точность"
          tone="mint"
          value={formatPercent(progress.weeklyAccuracy, locale)}
        />
        <ProgressMetric
          detail="Продолжайте!"
          icon="calendar"
          label="Текущая серия"
          tone="coral"
          value={formatStreak(progress.currentStreakDays, locale)}
        />
        <ProgressMetric
          detail="Всего"
          icon="clock"
          label="Время занятий"
          tone="sand"
          value={formatStudyTime(progress.totalStudyTimeSeconds, locale)}
        />
      </div>

      <section aria-labelledby="weekly-heading" className={styles.weeklySection}>
        <h3 id="weekly-heading">Активность за неделю</h3>
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
          <p className={styles.noActivity}>Пока нет данных об активности.</p>
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
  return (
    <div aria-label="Загрузка данных главной страницы" className={styles.contentGrid} role="status">
      <span className={styles.srOnly}>Загружаем данные…</span>
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
  return (
    <section className={styles.errorState}>
      <div className={styles.errorIcon}>
        <DashboardIcon name="book" />
      </div>
      <h2>Данные не загрузились</h2>
      <p>{getHomeErrorMessage(error)}</p>
      <button onClick={onRetry} type="button">
        Попробовать снова
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
