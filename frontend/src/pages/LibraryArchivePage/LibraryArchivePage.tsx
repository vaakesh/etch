import { Link } from "react-router-dom";
import { useSessionCacheScope } from "../../auth/hooks/useSessionCacheScope";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import { ArchiveDecksPanel } from "../LibraryPage/ArchiveDecksPanel";
import { ArchiveIcon } from "../LibraryPage/ArchiveIcon";
import styles from "../LibraryPage/LibraryPage.module.css";

const MESSAGES = defineMessages(
  { library: "Библиотека", title: "Архив колод", back: "Вернуться в библиотеку" },
  { library: "Library", title: "Deck archive", back: "Back to library" },
);

export default function LibraryArchivePage() {
  const messages = useLocalizedMessages(MESSAGES);
  const scope = useSessionCacheScope();
  return (
    <main className={styles.page} data-action-theme="aqua-flash">
      <section className={styles.library}>
        <Link aria-label={messages.back} className={styles.archiveBreadcrumb} to="/library/decks">
          <svg
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            viewBox="0 0 24 24"
          >
            <path d="m14 6-6 6 6 6M8 12h12" />
          </svg>
          {messages.library}
        </Link>
        <header className={`${styles.libraryHeader} ${styles.archivePageHeader}`}>
          <h1>{messages.title}</h1>
          <span className={styles.archivePageMark}>
            <ArchiveIcon />
          </span>
        </header>
        <ArchiveDecksPanel key={scope?.key ?? "signed-out"} />
      </section>
    </main>
  );
}
