import { useState } from "react";
import { isApiError } from "../../api";
import {
  clampPercent,
  formatCount,
  formatPercent,
  formatStreak,
  formatStudyTime,
} from "../../features/home/model/home-formatters";
import type { HomeDashboard, HomeDeck, HomeProgress } from "../../features/home/model/home-types";
import { useHomeDashboard } from "../../features/home/model/useHomeDashboard";
import { BrandMark, DashboardIcon, DeckIllustration, type DashboardIconName } from "./HomeVisuals";
import styles from "./HomePage.module.css";

interface NavigationItem {
  label: string;
  icon: DashboardIconName;
  active?: boolean;
}

const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { label: "Главная", icon: "home", active: true },
  { label: "Колоды", icon: "decks" },
  { label: "Библиотека", icon: "book" },
  { label: "Практика", icon: "practice" },
  { label: "Статистика", icon: "chart" },
  { label: "Настройки", icon: "settings" },
];

const WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"] as const;

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

interface SidebarProps {
  collapsed: boolean;
}

function Sidebar({ collapsed }: SidebarProps) {
  return (
    <aside className={styles.sidebar} id="home-sidebar">
      <div className={styles.brand}>
        <BrandMark className={styles.brandMark} />
        <span className={styles.brandName}>Etch</span>
      </div>

      <nav aria-label="Основная навигация" className={styles.navigation} id="home-navigation">
        <ul className={styles.navigationList}>
          {NAVIGATION_ITEMS.map((item) => (
            <li key={item.label}>
              {item.active ? (
                <a
                  aria-current="page"
                  aria-label={item.label}
                  className={styles.navigationItemActive}
                  href="/"
                  title={collapsed ? item.label : undefined}
                >
                  <DashboardIcon className={styles.navigationIcon} name={item.icon} />
                  <span className={styles.navigationLabel}>{item.label}</span>
                </a>
              ) : (
                <span
                  aria-label={item.label}
                  aria-disabled="true"
                  className={styles.navigationItem}
                  title={collapsed ? item.label : "Раздел пока не подключён"}
                >
                  <DashboardIcon className={styles.navigationIcon} name={item.icon} />
                  <span className={styles.navigationLabel}>{item.label}</span>
                </span>
              )}
            </li>
          ))}
        </ul>
      </nav>

      <div aria-hidden="true" className={styles.sidebarArtwork}>
        <DeckIllustration className={styles.sidebarIllustration} variant={5} />
        <span className={styles.artBook} />
        <span className={styles.artBookSecondary} />
      </div>
    </aside>
  );
}

function DashboardHeader() {
  return (
    <header className={styles.header}>
      <h1>Главная</h1>

      <div className={styles.headerActions}>
        <button
          className={styles.newDeckButton}
          disabled
          title="Создание колоды не входит в данные /bff/home"
          type="button"
        >
          <DashboardIcon name="plus" />
          <span>Новая колода</span>
        </button>
      </div>
    </header>
  );
}

interface DeckCardProps {
  deck: HomeDeck;
  index: number;
}

function DeckCard({ deck, index }: DeckCardProps) {
  const progress = clampPercent(deck.accuracy);

  return (
    <article className={styles.deckCard}>
      <div className={styles.deckCopy}>
        <h3>{deck.title}</h3>
        <p>{deck.description ?? "Без описания"}</p>
      </div>

      <div className={styles.deckBody}>
        <div className={styles.deckStats}>
          <p>
            <strong>{formatCount(deck.totalWordsCount)}</strong> слов
          </p>
          <strong className={styles.deckAccuracy}>{formatPercent(progress)}</strong>
          <div
            aria-label={`Прогресс ${formatPercent(progress)}`}
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={progress}
            className={styles.progressTrack}
            role="progressbar"
          >
            <span style={{ width: `${progress}%` }} />
          </div>
        </div>
        <DeckIllustration className={styles.deckIllustration} variant={index} />
      </div>

      <button
        aria-label={`Начать колоду «${deck.title}» — пока недоступно`}
        className={styles.startButton}
        disabled
        title="BFF пока не возвращает идентификатор колоды"
        type="button"
      >
        Начать
      </button>
    </article>
  );
}

function EmptyDecks() {
  return (
    <div className={styles.emptyDecks}>
      <DeckIllustration className={styles.emptyIllustration} variant={0} />
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
          <span aria-hidden="true" className={styles.sectionAction}>
            Все колоды
            <DashboardIcon name="chevron" />
          </span>
        ) : null}
      </div>

      {decks.length > 0 ? (
        <div className={styles.decksGrid}>
          {decks.map((deck, index) => (
            <DeckCard deck={deck} index={index} key={`${deck.title}-${index}`} />
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
  weeklyActivity: readonly number[];
}

function ProgressPanel({ progress, weeklyActivity }: ProgressPanelProps) {
  const chartValues = weeklyActivity.slice(0, WEEKDAY_LABELS.length);

  return (
    <aside aria-labelledby="progress-heading" className={styles.progressPanel}>
      <h2 id="progress-heading">Ваш прогресс</h2>

      <div className={styles.metricsList}>
        <ProgressMetric
          detail="Всего"
          icon="book"
          label="Изучено слов"
          tone="teal"
          value={formatCount(progress.wordsExplored)}
        />
        <ProgressMetric
          detail="За неделю"
          icon="target"
          label="Точность"
          tone="mint"
          value={formatPercent(progress.weeklyAccuracy)}
        />
        <ProgressMetric
          detail="Продолжайте!"
          icon="flame"
          label="Текущая серия"
          tone="coral"
          value={formatStreak(progress.currentStreakDays)}
        />
        <ProgressMetric
          detail="Всего"
          icon="clock"
          label="Время занятий"
          tone="sand"
          value={formatStudyTime(progress.totalStudyTimeSeconds)}
        />
      </div>

      <section aria-labelledby="weekly-heading" className={styles.weeklySection}>
        <h3 id="weekly-heading">Активность за неделю</h3>
        {chartValues.length > 0 ? (
          <div className={styles.weeklyChart}>
            {chartValues.map((value, index) => {
              const percent = clampPercent(value);
              const weekday = WEEKDAY_LABELS[index];

              return (
                <div className={styles.weeklyBar} key={`${weekday}-${index}`}>
                  <div className={styles.barTrack}>
                    <span
                      aria-label={`${weekday}: ${formatPercent(percent)}`}
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
      <div className={styles.mainColumn}>
        <DecksSection decks={dashboard.decks} />
      </div>
      <ProgressPanel progress={dashboard.progress} weeklyActivity={dashboard.weeklyActivity} />
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div aria-label="Загрузка данных главной страницы" className={styles.contentGrid} role="status">
      <span className={styles.srOnly}>Загружаем данные…</span>
      <div className={styles.mainColumn}>
        <section className={styles.decksSection}>
          <div className={styles.skeletonHeading} />
          <div className={styles.decksGrid}>
            {Array.from({ length: 6 }, (_, index) => (
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
      <aside className={styles.skeletonPanel}>
        <span className={styles.skeletonLineWide} />
        {Array.from({ length: 4 }, (_, index) => (
          <span className={styles.skeletonMetric} key={index} />
        ))}
      </aside>
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
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const shellClassName = isSidebarCollapsed
    ? `${styles.shell} ${styles.shellCollapsed}`
    : styles.shell;

  return (
    <main className={styles.page}>
      <div className={shellClassName}>
        <button
          aria-controls="home-sidebar"
          aria-expanded={!isSidebarCollapsed}
          aria-label={isSidebarCollapsed ? "Развернуть боковое меню" : "Свернуть боковое меню"}
          className={styles.sidebarToggle}
          onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
          title={isSidebarCollapsed ? "Развернуть боковое меню" : "Свернуть боковое меню"}
          type="button"
        >
          <DashboardIcon className={styles.sidebarToggleIcon} name="chevron" />
        </button>
        <Sidebar collapsed={isSidebarCollapsed} />
        <section className={styles.dashboard}>
          <DashboardHeader />
          {status === "loading" ? <DashboardSkeleton /> : null}
          {status === "error" && error !== null ? (
            <ErrorState error={error} onRetry={retry} />
          ) : null}
          {status === "success" && data !== null ? <DashboardContent dashboard={data} /> : null}
        </section>
      </div>
    </main>
  );
}

export default HomePage;
