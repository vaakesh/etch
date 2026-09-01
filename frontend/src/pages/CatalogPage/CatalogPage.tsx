import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { isApiError } from "../../api";
import { useAuth } from "../../auth/hooks/useAuth";
import { DashboardIcon } from "../../components/DashboardVisuals";
import { CATALOG_SEARCH_MAX_LENGTH } from "../../features/catalog/api/catalog-api";
import type { CatalogDeck } from "../../features/catalog/model/catalog-types";
import {
  getCatalogPaginationTokens,
  parseCatalogPage,
} from "../../features/catalog/model/catalog-pagination";
import {
  useCatalogDecks,
  type CatalogDeckSaveFailure,
} from "../../features/catalog/model/useCatalogDecks";
import {
  WORD_COUNT_FORMS,
  defineMessages,
  localizeCount,
  useLocale,
  useLocalizedMessages,
  type LocalizedCountForms,
} from "../../i18n";
import { CatalogDeckPreview } from "./CatalogDeckPreview";
import styles from "./CatalogPage.module.css";

const SAVE_COUNT_FORMS = {
  "ru-RU": {
    one: "сохранение",
    few: "сохранения",
    many: "сохранений",
    other: "сохранения",
  },
  "en-US": { one: "save", other: "saves" },
} satisfies LocalizedCountForms;

const MESSAGES = defineMessages(
  {
    title: "Каталог",
    searchLabel: "Поиск по названию колоды",
    searchPlaceholder: "Найти колоду",
    clearSearch: "Очистить поиск",
    save: "Сохранить",
    saved: "Сохранено",
    inLibrary: "В библиотеке",
    ownDeckInLibrary: (title: string) => `Колода «${title}» уже в вашей библиотеке`,
    saveDeck: (title: string) => `Сохранить колоду «${title}»`,
    unsaveDeck: (title: string) => `Убрать колоду «${title}» из сохранённых`,
    saveError: (title: string, reason: string) =>
      `Колоду «${title}» не удалось сохранить. Ошибка: ${reason}`,
    unsaveError: (title: string, reason: string) =>
      `Колоду «${title}» не удалось убрать из сохранённых. Ошибка: ${reason}`,
    saveErrorReasons: {
      generic: "непредвиденная ошибка. Попробуйте ещё раз.",
      forbidden: "недостаточно прав для этого действия.",
      notFound: "колода больше недоступна.",
      conflict: "действие недоступно для этой колоды.",
      invalid: "не удалось обработать запрос.",
      network: "нет связи с сервером.",
      server: "сервер временно недоступен.",
    },
    yourDeck: "Ваша колода",
    otherOwner: "Другой пользователь",
    noDescription: "Без описания",
    preview: "Предпросмотр",
    previewDeck: (title: string) => `Предпросмотр колоды «${title}»`,
    loading: "Загружаем каталог…",
    empty: "Публичных колод пока нет",
    searchEmpty: "Ничего не найдено",
    pageEmpty: "На этой странице нет колод",
    errorTitle: "Каталог не загрузился",
    retry: "Попробовать снова",
    pagination: "Страницы каталога",
    goToPage: (page: number) => `Перейти на страницу ${page}`,
    currentPage: (page: number) => `Страница ${page}, текущая`,
    pageStatus: (page: number) => `Страница ${page}`,
    errors: {
      generic: "Попробуйте ещё раз.",
      forbidden: "У этой учётной записи нет доступа к каталогу.",
      invalid: "Сервер вернул данные в неожиданном формате.",
      network: "Не удалось связаться с сервером.",
      server: "Сервер временно недоступен.",
    },
  },
  {
    title: "Catalog",
    searchLabel: "Search decks by title",
    searchPlaceholder: "Find a deck",
    clearSearch: "Clear search",
    save: "Save",
    saved: "Saved",
    inLibrary: "In library",
    ownDeckInLibrary: (title: string) => `“${title}” is already in your library`,
    saveDeck: (title: string) => `Save “${title}”`,
    unsaveDeck: (title: string) => `Remove “${title}” from saved decks`,
    saveError: (title: string, reason: string) => `Could not save “${title}”. Error: ${reason}`,
    unsaveError: (title: string, reason: string) =>
      `Could not remove “${title}” from saved decks. Error: ${reason}`,
    saveErrorReasons: {
      generic: "an unexpected error occurred. Try again.",
      forbidden: "you don't have permission for this action.",
      notFound: "the deck is no longer available.",
      conflict: "this action is unavailable for the deck.",
      invalid: "the request could not be processed.",
      network: "the server could not be reached.",
      server: "the server is temporarily unavailable.",
    },
    yourDeck: "Your deck",
    otherOwner: "Another user",
    noDescription: "No description",
    preview: "Preview",
    previewDeck: (title: string) => `Preview “${title}”`,
    loading: "Loading catalog…",
    empty: "No public decks yet",
    searchEmpty: "Nothing found",
    pageEmpty: "There are no decks on this page",
    errorTitle: "Catalog didn't load",
    retry: "Try again",
    pagination: "Catalog pages",
    goToPage: (page: number) => `Go to page ${page}`,
    currentPage: (page: number) => `Page ${page}, current`,
    pageStatus: (page: number) => `Page ${page}`,
    errors: {
      generic: "Try again.",
      forbidden: "This account does not have access to the catalog.",
      invalid: "The server returned unexpected data.",
      network: "Couldn't reach the server.",
      server: "The server is temporarily unavailable.",
    },
  },
);

type CatalogIconName = "check" | "eye" | "heart" | "search" | "user" | "x";

function CatalogIcon({ name }: { name: CatalogIconName }) {
  let content;

  if (name === "search") {
    content = (
      <>
        <circle cx="10.8" cy="10.8" r="6.5" />
        <path d="m15.7 15.7 4.3 4.3" />
      </>
    );
  } else if (name === "x") {
    content = <path d="m7 7 10 10M17 7 7 17" />;
  } else if (name === "user") {
    content = (
      <>
        <circle cx="12" cy="8.2" r="3.2" />
        <path d="M5.5 20c.5-4 2.7-6.1 6.5-6.1S18 16 18.5 20" />
      </>
    );
  } else if (name === "heart") {
    content = (
      <path d="M12 20S4.5 15.8 4.5 9.8A4.3 4.3 0 0 1 12 6.9a4.3 4.3 0 0 1 7.5 2.9C19.5 15.8 12 20 12 20Z" />
    );
  } else if (name === "check") {
    content = <path d="m6.5 12.5 3.5 3.5 7.5-8" />;
  } else {
    content = (
      <>
        <path d="M2.8 12s3.3-5.4 9.2-5.4 9.2 5.4 9.2 5.4-3.3 5.4-9.2 5.4S2.8 12 2.8 12Z" />
        <circle cx="12" cy="12" r="2.4" />
      </>
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
      {content}
    </svg>
  );
}

function getCatalogErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.generic;
  }
  if (error.status === 403) {
    return messages.errors.forbidden;
  }
  if (error.code === "INVALID_CATALOG_RESPONSE") {
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

function getCatalogSaveErrorMessage(
  deckTitle: string,
  failure: CatalogDeckSaveFailure,
  messages: (typeof MESSAGES)["ru-RU"],
): string {
  let reason = messages.saveErrorReasons.generic;

  if (isApiError(failure.error)) {
    if (failure.error.status === 403) {
      reason = messages.saveErrorReasons.forbidden;
    } else if (failure.error.status === 404) {
      reason = messages.saveErrorReasons.notFound;
    } else if (failure.error.status === 409) {
      reason = messages.saveErrorReasons.conflict;
    } else if (failure.error.status === 422) {
      reason = messages.saveErrorReasons.invalid;
    } else if (failure.error.code === "NETWORK_ERROR") {
      reason = messages.saveErrorReasons.network;
    } else if (failure.error.status >= 500) {
      reason = messages.saveErrorReasons.server;
    }
  }

  return failure.intendedSavedState
    ? messages.saveError(deckTitle, reason)
    : messages.unsaveError(deckTitle, reason);
}

function CatalogDeckCard({
  deck,
  currentUserUuid,
  isSaving,
  onPreview,
  onSavedChange,
  saveFailure,
}: {
  deck: CatalogDeck;
  currentUserUuid: string;
  isSaving: boolean;
  onPreview: (deckUuid: string, trigger: HTMLButtonElement) => void;
  onSavedChange: (deckUuid: string, value: boolean) => void;
  saveFailure: CatalogDeckSaveFailure | null;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const words = localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale);
  const saves = localizeCount(deck.savesCount, SAVE_COUNT_FORMS, locale);
  const ownerUsername =
    deck.ownerUuid === currentUserUuid ? messages.yourDeck : messages.otherOwner;
  const isOwnDeck = deck.ownerUuid === currentUserUuid;
  const saveErrorId = `catalog-save-error-${deck.uuid}`;
  const saveButtonClassName = deck.isSaved
    ? `${styles.saveButton} ${styles.saveButtonActive}`
    : styles.saveButton;

  return (
    <article className={styles.deckCard} data-deck-uuid={deck.uuid}>
      <div className={styles.deckHeader}>
        <div className={styles.deckTitleBlock}>
          <h2>{deck.title}</h2>
          <span className={styles.owner}>
            <CatalogIcon name="user" />
            <span>{ownerUsername}</span>
          </span>
        </div>
        {isOwnDeck ? (
          <span aria-label={messages.ownDeckInLibrary(deck.title)} className={styles.ownDeckBadge}>
            <CatalogIcon name="check" />
            <span>{messages.inLibrary}</span>
          </span>
        ) : (
          <button
            aria-busy={isSaving}
            aria-describedby={saveFailure === null ? undefined : saveErrorId}
            aria-label={
              deck.isSaved ? messages.unsaveDeck(deck.title) : messages.saveDeck(deck.title)
            }
            aria-pressed={deck.isSaved}
            className={saveButtonClassName}
            disabled={isSaving}
            onClick={() => onSavedChange(deck.uuid, !deck.isSaved)}
            type="button"
          >
            {isSaving ? <span aria-hidden="true" className={styles.saveSpinner} /> : null}
            <span>{deck.isSaved ? messages.saved : messages.save}</span>
          </button>
        )}
      </div>

      {saveFailure === null ? null : (
        <p className={styles.saveError} id={saveErrorId} role="alert">
          {getCatalogSaveErrorMessage(deck.title, saveFailure, messages)}
        </p>
      )}

      <p className={styles.description}>{deck.description ?? messages.noDescription}</p>

      <div className={styles.stats}>
        <span>
          <DashboardIcon name="book" />
          {words.text}
        </span>
        <span>
          <CatalogIcon name="heart" />
          {saves.text}
        </span>
      </div>

      <footer className={styles.footer}>
        <button
          aria-label={messages.previewDeck(deck.title)}
          className={styles.previewButton}
          onClick={(event) => onPreview(deck.uuid, event.currentTarget)}
          type="button"
        >
          <CatalogIcon name="eye" />
          <span>{messages.preview}</span>
        </button>
      </footer>
    </article>
  );
}

function CatalogSkeletons() {
  return (
    <div aria-hidden="true" className={styles.grid}>
      {Array.from({ length: 6 }, (_, index) => (
        <div className={styles.skeleton} key={index} />
      ))}
    </div>
  );
}

function CatalogPagination({
  currentPage,
  pageCount,
  onPageChange,
}: {
  currentPage: number;
  pageCount: number;
  onPageChange: (page: number) => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const tokens = getCatalogPaginationTokens(pageCount, currentPage);

  if (tokens.filter((token) => token.type === "page").length < 2) {
    return null;
  }

  return (
    <nav aria-label={messages.pagination} className={styles.pagination}>
      <span aria-live="polite" className={styles.visuallyHidden} role="status">
        {messages.pageStatus(currentPage)}
      </span>
      <ol className={styles.paginationList}>
        {tokens.map((token) => (
          <li key={token.key}>
            {token.type === "ellipsis" ? (
              <span aria-hidden="true" className={styles.paginationEllipsis}>
                …
              </span>
            ) : (
              <button
                aria-current={token.pageNumber === currentPage ? "page" : undefined}
                aria-label={
                  token.pageNumber === currentPage
                    ? messages.currentPage(token.pageNumber)
                    : messages.goToPage(token.pageNumber)
                }
                className={
                  token.pageNumber === currentPage
                    ? `${styles.paginationButton} ${styles.paginationButtonActive}`
                    : styles.paginationButton
                }
                onClick={() => onPageChange(token.pageNumber)}
                type="button"
              >
                {token.pageNumber}
              </button>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function CatalogPage() {
  const messages = useLocalizedMessages(MESSAGES);
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState("");
  const [previewDeckUuid, setPreviewDeckUuid] = useState<string | null>(null);
  const pageRef = useRef<HTMLElement | null>(null);
  const pageScrollTopRef = useRef<number | null>(null);
  const previewTriggerRef = useRef<HTMLButtonElement | null>(null);
  const currentPage = parseCatalogPage(searchParams.get("page"));
  const catalog = useCatalogDecks(searchQuery, currentPage);
  const pageCount = currentPage + (catalog.status === "success" && catalog.hasMore ? 1 : 0);
  const isSearchActive = searchQuery.trim().length > 0;
  const currentUserUuid = user?.uuid ?? "";

  function changePage(page: number, replace = false): void {
    const nextSearchParams = new URLSearchParams(searchParams);
    if (page === 1) {
      nextSearchParams.delete("page");
    } else {
      nextSearchParams.set("page", String(page));
    }
    setSearchParams(nextSearchParams, { replace });
  }

  function handleSearchChange(value: string): void {
    setSearchQuery(value);
    if (currentPage !== 1) {
      changePage(1, true);
    }
  }

  function handlePageChange(page: number): void {
    if (page === currentPage) {
      return;
    }

    changePage(page);
    const scrollBehavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth";
    pageRef.current?.scrollTo({ top: 0, behavior: scrollBehavior });
  }

  useEffect(() => {
    if (previewDeckUuid === null) {
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
  }, [previewDeckUuid]);

  useEffect(() => {
    if (previewDeckUuid !== null || previewTriggerRef.current === null) {
      return;
    }

    previewTriggerRef.current.focus({ preventScroll: true });
    previewTriggerRef.current = null;
  }, [previewDeckUuid]);

  function openPreview(deckUuid: string, trigger: HTMLButtonElement): void {
    pageScrollTopRef.current = pageRef.current?.scrollTop ?? null;
    previewTriggerRef.current = trigger;
    setPreviewDeckUuid(deckUuid);
  }

  return (
    <main className={styles.page} ref={pageRef}>
      <div className={styles.catalog}>
        <header className={styles.header}>
          <h1>{messages.title}</h1>
          <div className={styles.searchField}>
            <label>
              <span className={styles.visuallyHidden}>{messages.searchLabel}</span>
              <CatalogIcon name="search" />
              <input
                autoComplete="off"
                maxLength={CATALOG_SEARCH_MAX_LENGTH}
                name="catalog_search"
                onChange={(event) => handleSearchChange(event.currentTarget.value)}
                placeholder={messages.searchPlaceholder}
                type="search"
                value={searchQuery}
              />
            </label>
            {searchQuery.length > 0 ? (
              <button
                aria-label={messages.clearSearch}
                className={styles.clearSearch}
                onClick={() => handleSearchChange("")}
                type="button"
              >
                <CatalogIcon name="x" />
              </button>
            ) : null}
          </div>
        </header>

        <section aria-busy={catalog.status === "loading"}>
          {catalog.status === "loading" ? (
            <div aria-label={messages.loading} role="status">
              <CatalogSkeletons />
            </div>
          ) : null}

          {catalog.status === "error" ? (
            <div className={styles.stateMessage} role="alert">
              <h2>{messages.errorTitle}</h2>
              <p>{getCatalogErrorMessage(catalog.error, messages)}</p>
              <button onClick={catalog.retry} type="button">
                {messages.retry}
              </button>
            </div>
          ) : null}

          {catalog.status === "success" && catalog.decks.length === 0 ? (
            <div className={styles.stateMessage} role="status">
              <h2>
                {currentPage > 1
                  ? messages.pageEmpty
                  : isSearchActive
                    ? messages.searchEmpty
                    : messages.empty}
              </h2>
            </div>
          ) : null}

          {catalog.status === "success" && catalog.decks.length > 0 ? (
            <>
              <div className={styles.grid}>
                {catalog.decks.map((deck) => (
                  <CatalogDeckCard
                    currentUserUuid={currentUserUuid}
                    deck={deck}
                    isSaving={catalog.savingDeckUuids.includes(deck.uuid)}
                    key={deck.uuid}
                    onPreview={openPreview}
                    onSavedChange={catalog.setSaved}
                    saveFailure={catalog.saveErrors[deck.uuid] ?? null}
                  />
                ))}
              </div>
            </>
          ) : null}

          <CatalogPagination
            currentPage={currentPage}
            onPageChange={handlePageChange}
            pageCount={pageCount}
          />
        </section>
      </div>
      {previewDeckUuid === null ? null : (
        <CatalogDeckPreview
          currentUserUuid={currentUserUuid}
          deckUuid={previewDeckUuid}
          onClose={() => setPreviewDeckUuid(null)}
        />
      )}
    </main>
  );
}

export default CatalogPage;
