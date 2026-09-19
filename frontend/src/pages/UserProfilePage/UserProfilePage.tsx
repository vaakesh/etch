import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { isApiError } from "../../api";
import { useAuth } from "../../auth/hooks/useAuth";
import { DashboardIcon } from "../../components/DashboardVisuals";
import type { UserProfileDeck } from "../../features/users/model/user-profile-types";
import { useUserProfile } from "../../features/users/model/useUserProfile";
import {
  createDeckDetailsNavigationState,
  getDeckDetailsPath,
} from "../../features/decks/model/deck-details-navigation";
import {
  WORD_COUNT_FORMS,
  defineMessages,
  formatNumber,
  localizeCount,
  useLocale,
  useLocalizedMessages,
  type AppLocale,
  type LocalizedCountForms,
} from "../../i18n";
import { CatalogDeckPreview } from "../CatalogPage/CatalogDeckPreview";
import catalogStyles from "../CatalogPage/CatalogPage.module.css";
import styles from "./UserProfilePage.module.css";

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
    eyebrow: "Профиль пользователя",
    ownEyebrow: "Ваш профиль",
    ownBadge: "Это вы",
    joined: "В Etch с",
    decksStat: "Колоды",
    savesStat: "Сохранения колод",
    decksTitle: "Колоды пользователя",
    ownDecksTitle: "Ваши колоды",
    shownDecks: (shown: string, total: string) => `Показано ${shown} из ${total}`,
    save: "Сохранить",
    saved: "Сохранено",
    inLibrary: "В библиотеке",
    ownDeckInLibrary: (title: string) => `Колода «${title}» уже в вашей библиотеке`,
    saveDeck: (title: string) => `Сохранить колоду «${title}»`,
    unsaveDeck: (title: string) => `Убрать колоду «${title}» из сохранённых`,
    noDescription: "Без описания",
    openDeckPage: (title: string) => `Открыть страницу колоды «${title}»`,
    preview: "Предпросмотр",
    previewDeck: (title: string) => `Предпросмотр колоды «${title}»`,
    start: "Начать тренировку",
    configurePractice: (title: string) => `Настроить тренировку по колоде «${title}»`,
    emptyTitle: "Здесь пока нет колод",
    emptyDescription: "Когда пользователь создаст доступную вам колоду, она появится здесь.",
    ownEmptyTitle: "У вас пока нет колод",
    ownEmptyDescription: "Созданные вами колоды появятся здесь.",
    loading: "Загружаем профиль…",
    errorTitle: "Профиль не загрузился",
    retry: "Попробовать снова",
    loadMore: "Показать ещё",
    loadingMore: "Загружаем…",
    loadMoreError: "Не удалось загрузить следующие колоды.",
    errors: {
      generic: "Попробуйте ещё раз.",
      notFound: "Пользователь с таким никнеймом не найден.",
      invalid: "Сервер вернул данные в неожиданном формате.",
      network: "Не удалось связаться с сервером.",
      server: "Сервер временно недоступен.",
    },
  },
  {
    eyebrow: "User profile",
    ownEyebrow: "Your profile",
    ownBadge: "This is you",
    joined: "On Etch since",
    decksStat: "Decks",
    savesStat: "Deck saves",
    decksTitle: "User decks",
    ownDecksTitle: "Your decks",
    shownDecks: (shown: string, total: string) => `Showing ${shown} of ${total}`,
    save: "Save",
    saved: "Saved",
    inLibrary: "In library",
    ownDeckInLibrary: (title: string) => `“${title}” is already in your library`,
    saveDeck: (title: string) => `Save “${title}”`,
    unsaveDeck: (title: string) => `Remove “${title}” from saved decks`,
    noDescription: "No description",
    openDeckPage: (title: string) => `Open the “${title}” deck page`,
    preview: "Preview",
    previewDeck: (title: string) => `Preview “${title}”`,
    start: "Start practice",
    configurePractice: (title: string) => `Configure practice for “${title}”`,
    emptyTitle: "No decks here yet",
    emptyDescription: "When this user creates a deck available to you, it will appear here.",
    ownEmptyTitle: "You don't have any decks yet",
    ownEmptyDescription: "Decks you create will appear here.",
    loading: "Loading profile…",
    errorTitle: "The profile didn't load",
    retry: "Try again",
    loadMore: "Show more",
    loadingMore: "Loading…",
    loadMoreError: "Couldn't load the next decks.",
    errors: {
      generic: "Try again.",
      notFound: "No user with this username was found.",
      invalid: "The server returned unexpected data.",
      network: "Couldn't reach the server.",
      server: "The server is temporarily unavailable.",
    },
  },
);

type ProfileIconName = "arrow" | "calendar" | "check" | "external" | "eye" | "heart";

function ProfileIcon({ name }: { name: ProfileIconName }) {
  let content;

  if (name === "heart") {
    content = (
      <path d="M12 20S4.5 15.8 4.5 9.8A4.3 4.3 0 0 1 12 6.9a4.3 4.3 0 0 1 7.5 2.9C19.5 15.8 12 20 12 20Z" />
    );
  } else if (name === "check") {
    content = <path d="m6.5 12.5 3.5 3.5 7.5-8" />;
  } else if (name === "eye") {
    content = (
      <>
        <path d="M2.8 12s3.3-5.4 9.2-5.4 9.2 5.4 9.2 5.4-3.3 5.4-9.2 5.4S2.8 12 2.8 12Z" />
        <circle cx="12" cy="12" r="2.4" />
      </>
    );
  } else if (name === "external") {
    content = <path d="M7 17 17 7M8 7h9v9" />;
  } else if (name === "calendar") {
    content = (
      <>
        <rect height="15" rx="2.5" width="17" x="3.5" y="5.5" />
        <path d="M7.5 3.5v4M16.5 3.5v4M3.5 10h17" />
      </>
    );
  } else {
    content = <path d="M5 12h14m-6-6 6 6-6 6" />;
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

const createdAtFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

function formatCreatedAt(value: string, locale: AppLocale): string {
  let formatter = createdAtFormatters.get(locale);
  if (formatter === undefined) {
    formatter = new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
    createdAtFormatters.set(locale, formatter);
  }

  return formatter.format(new Date(value));
}

function getProfileErrorMessage(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): string {
  if (!isApiError(error)) {
    return messages.errors.generic;
  }
  if (error.status === 404 || error.status === 422) {
    return messages.errors.notFound;
  }
  if (error.code === "INVALID_USER_PROFILE_RESPONSE") {
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

function UserDeckCard({
  currentUserUuid,
  deck,
  onPreview,
  onSavedChange,
}: {
  currentUserUuid: string;
  deck: UserProfileDeck;
  onPreview: (deckUuid: string) => void;
  onSavedChange: (deckUuid: string, value: boolean) => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const words = localizeCount(deck.totalWordsCount, WORD_COUNT_FORMS, locale);
  const saves = localizeCount(deck.savesCount, SAVE_COUNT_FORMS, locale);
  const isOwnDeck = deck.ownerUuid === currentUserUuid;
  const saveButtonClassName = deck.isSaved
    ? `${catalogStyles.saveButton} ${catalogStyles.saveButtonActive}`
    : catalogStyles.saveButton;

  return (
    <article className={catalogStyles.deckCard} data-deck-uuid={deck.uuid}>
      <div className={catalogStyles.deckHeader}>
        <div className={catalogStyles.deckTitleBlock}>
          <h2>
            <Link
              aria-label={messages.openDeckPage(deck.title)}
              className={catalogStyles.deckDetailsLink}
              state={createDeckDetailsNavigationState("profile", deck.ownerUsername)}
              to={getDeckDetailsPath(deck.uuid)}
            >
              <span className={catalogStyles.deckDetailsText}>{deck.title}</span>
              <ProfileIcon name="external" />
            </Link>
          </h2>
          <Link
            className={`${catalogStyles.owner} ${styles.ownerLink}`}
            to={`/users/${encodeURIComponent(deck.ownerUsername)}`}
          >
            <span>@{deck.ownerUsername}</span>
          </Link>
        </div>
        {isOwnDeck ? (
          <span
            aria-label={messages.ownDeckInLibrary(deck.title)}
            className={catalogStyles.ownDeckBadge}
          >
            <ProfileIcon name="check" />
            <span>{messages.inLibrary}</span>
          </span>
        ) : (
          <button
            aria-label={
              deck.isSaved ? messages.unsaveDeck(deck.title) : messages.saveDeck(deck.title)
            }
            aria-pressed={deck.isSaved}
            className={saveButtonClassName}
            data-save-theme="berry-blush"
            onClick={() => onSavedChange(deck.uuid, !deck.isSaved)}
            type="button"
          >
            <span>{deck.isSaved ? messages.saved : messages.save}</span>
            <ProfileIcon name={deck.isSaved ? "check" : "heart"} />
          </button>
        )}
      </div>

      <p className={catalogStyles.description}>{deck.description ?? messages.noDescription}</p>

      <div className={catalogStyles.stats}>
        <span>
          <DashboardIcon name="book" />
          {words.text}
        </span>
        <span>
          <ProfileIcon name="heart" />
          {saves.text}
        </span>
      </div>

      <footer className={catalogStyles.footer}>
        <button
          aria-label={messages.previewDeck(deck.title)}
          className={catalogStyles.previewButton}
          onClick={() => onPreview(deck.uuid)}
          type="button"
        >
          <ProfileIcon name="eye" />
          <span>{messages.preview}</span>
        </button>
        <Link
          aria-label={messages.configurePractice(deck.title)}
          className={catalogStyles.startButton}
          to={`/practice?deck=${encodeURIComponent(deck.uuid)}`}
        >
          <span>{messages.start}</span>
          <ProfileIcon name="arrow" />
        </Link>
      </footer>
    </article>
  );
}

function ProfileSkeleton({ label }: { label: string }) {
  return (
    <div aria-label={label} className={styles.loading} role="status">
      <div className={styles.heroSkeleton} />
      <div aria-hidden="true" className={catalogStyles.grid}>
        {Array.from({ length: 6 }, (_, index) => (
          <div className={catalogStyles.skeleton} key={index} />
        ))}
      </div>
    </div>
  );
}

export function UserProfilePage() {
  const { username = "" } = useParams<{ username: string }>();
  const messages = useLocalizedMessages(MESSAGES);
  const { locale } = useLocale();
  const { user } = useAuth();
  const profileState = useUserProfile(username);
  const [previewDeckUuid, setPreviewDeckUuid] = useState<string | null>(null);
  const profile = profileState.profile;
  const isOwnProfile =
    user !== null && profile !== null && user.uuid.toLowerCase() === profile.uuid.toLowerCase();

  return (
    <main
      className={`${catalogStyles.page} ${styles.profilePage}`}
      data-preview-start-theme="aqua-breeze"
    >
      <div className={styles.profile}>
        {profileState.status === "loading" ? <ProfileSkeleton label={messages.loading} /> : null}

        {profileState.status === "error" ? (
          <section className={styles.state} role="alert">
            <span aria-hidden="true" className={styles.stateMark}>
              !
            </span>
            <h1>{messages.errorTitle}</h1>
            <p>{getProfileErrorMessage(profileState.error, messages)}</p>
            <button onClick={profileState.retry} type="button">
              {messages.retry}
            </button>
          </section>
        ) : null}

        {profileState.status === "success" && profile !== null ? (
          <div className={styles.content}>
            <header
              className={isOwnProfile ? `${styles.hero} ${styles.ownHero}` : styles.hero}
              data-own-profile={isOwnProfile ? "true" : undefined}
            >
              <div aria-hidden="true" className={styles.avatar}>
                {Array.from(profile.username)[0]?.toLocaleUpperCase(locale) ?? "U"}
              </div>
              <div className={styles.identity}>
                <div className={styles.identityMeta}>
                  <span className={styles.eyebrow}>
                    {isOwnProfile ? messages.ownEyebrow : messages.eyebrow}
                  </span>
                  {isOwnProfile ? (
                    <span className={styles.ownBadge}>
                      <ProfileIcon name="check" />
                      {messages.ownBadge}
                    </span>
                  ) : null}
                </div>
                <h1>@{profile.username}</h1>
                <p className={styles.joinedAt}>
                  <ProfileIcon name="calendar" />
                  <span>{messages.joined}</span>
                  <time dateTime={profile.createdAt}>
                    {formatCreatedAt(profile.createdAt, locale)}
                  </time>
                </p>
              </div>
              <dl className={styles.summary}>
                <div>
                  <dt>{messages.decksStat}</dt>
                  <dd>{formatNumber(profile.deckCount, locale)}</dd>
                </div>
                <div>
                  <dt>{messages.savesStat}</dt>
                  <dd>{formatNumber(profile.totalSavesCount, locale)}</dd>
                </div>
              </dl>
            </header>

            <section aria-labelledby="user-decks-title" className={styles.decksSection}>
              <div className={styles.sectionHeader}>
                <h2 id="user-decks-title">
                  {isOwnProfile ? messages.ownDecksTitle : messages.decksTitle}
                </h2>
                {profile.deckCount > 0 ? (
                  <p>
                    {messages.shownDecks(
                      formatNumber(profileState.decks.length, locale),
                      formatNumber(profile.deckCount, locale),
                    )}
                  </p>
                ) : null}
              </div>

              {profileState.decks.length === 0 ? (
                <div className={styles.emptyState}>
                  <span aria-hidden="true" className={styles.emptyIcon}>
                    <DashboardIcon name="decks" />
                  </span>
                  <h3>{isOwnProfile ? messages.ownEmptyTitle : messages.emptyTitle}</h3>
                  <p>{isOwnProfile ? messages.ownEmptyDescription : messages.emptyDescription}</p>
                </div>
              ) : (
                <div className={catalogStyles.grid}>
                  {profileState.decks.map((deck) => (
                    <UserDeckCard
                      currentUserUuid={user?.uuid ?? ""}
                      deck={deck}
                      key={deck.uuid}
                      onPreview={setPreviewDeckUuid}
                      onSavedChange={profileState.setMockSaved}
                    />
                  ))}
                </div>
              )}

              {profileState.hasMore || profileState.loadMoreError !== null ? (
                <div className={styles.loadMore}>
                  {profileState.loadMoreError === null ? null : (
                    <p role="alert">{messages.loadMoreError}</p>
                  )}
                  <button
                    disabled={profileState.isLoadingMore}
                    onClick={profileState.loadMore}
                    type="button"
                  >
                    {profileState.isLoadingMore ? messages.loadingMore : messages.loadMore}
                  </button>
                </div>
              ) : null}
            </section>
          </div>
        ) : null}
      </div>

      {previewDeckUuid === null ? null : (
        <CatalogDeckPreview
          deckUuid={previewDeckUuid}
          onClose={() => setPreviewDeckUuid(null)}
          returnTarget="profile"
          returnUsername={profile?.username}
        />
      )}
    </main>
  );
}

export default UserProfilePage;
