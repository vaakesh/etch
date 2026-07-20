import { useState, type KeyboardEvent } from "react";
import { isApiError } from "../../api";
import { DashboardIcon } from "../../components/DashboardVisuals";
import type { LibraryDeck } from "../../features/library/model/library-types";
import { useLibraryDecks } from "../../features/library/model/useLibraryDecks";
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

  return (
    <div
      aria-label={`Точность ${value}%`}
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={value}
      className={`${styles.accuracy} ${styles[`accuracy${tone}`]}`}
      role="meter"
    >
      <span aria-hidden="true" className={styles.accuracyIcon}>
        <DashboardIcon name="target" />
      </span>
      <span className={styles.accuracyLabel}>Точность пользователя:</span>
      <strong>{value}%</strong>
    </div>
  );
}

function DeckCard({ deck }: { deck: LibraryDeck }) {
  const previewCards = deck.cards.slice(0, 2);

  return (
    <article className={styles.deckCard} data-deck-uuid={deck.uuid}>
      <div className={styles.deckTopline}>
        <AccuracyStat value={deck.accuracy} />
        <span
          aria-label={deck.isFavourite ? "В избранном" : "Не в избранном"}
          className={deck.isFavourite ? styles.favouriteActive : styles.favourite}
          title={deck.isFavourite ? "В избранном" : "Не в избранном"}
        >
          <Glyph name="heart" />
        </span>
      </div>

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
        <button
          aria-label={`Изменить колоду «${deck.title}» — пока недоступно`}
          className={styles.editButton}
          disabled
          title="Редактирование колоды пока не подключено"
          type="button"
        >
          <Glyph name="pencil" />
          <span>Редактировать</span>
        </button>
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
          <time dateTime={deck.updatedAt ?? undefined}>{formatUpdatedAt(deck.updatedAt)}</time>
        </span>
      </footer>
    </article>
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

export function LibraryPage() {
  const [activeView, setActiveView] = useState<LibraryView>("decks");
  const library = useLibraryDecks();

  return (
    <main className={styles.page}>
      <section className={styles.library}>
        <header className={styles.libraryHeader}>
          <div>
            <span className={styles.eyebrow}>Ваше пространство</span>
            <h1>Библиотека</h1>
          </div>
          <button
            className={styles.newDeckButton}
            disabled
            title="Создание колоды пока не подключено"
            type="button"
          >
            <DashboardIcon name="plus" />
            <span>Новая колода</span>
          </button>
        </header>

        <div className={styles.toolbar}>
          <LibraryTabs activeView={activeView} onChange={setActiveView} />
          {activeView === "decks" && library.status === "success" ? (
            <div aria-live="polite" className={styles.summary}>
              <Glyph name="sparkles" />
              <span>
                <strong>{library.decks.length}</strong> колод загружено
              </span>
            </div>
          ) : null}
        </div>

        <section
          aria-labelledby="library-decks-tab"
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
              title="Библиотека не загрузилась"
            />
          ) : null}
          {library.status === "success" && library.decks.length === 0 ? (
            <StateMessage
              description="Когда у вас появятся колоды, они соберутся здесь."
              title="В библиотеке пока пусто"
            />
          ) : null}
          {library.status === "success" && library.decks.length > 0 ? (
            <>
              <div className={styles.decksGrid}>
                {library.decks.map((deck) => (
                  <DeckCard deck={deck} key={deck.uuid} />
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

        <section
          aria-labelledby="library-cards-tab"
          className={styles.cardsPanel}
          hidden={activeView !== "cards"}
          id="library-cards-panel"
          role="tabpanel"
        />
      </section>
    </main>
  );
}

export default LibraryPage;
