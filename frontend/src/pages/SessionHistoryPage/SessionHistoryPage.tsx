import { Link, useParams } from "react-router-dom";
import { isApiError } from "../../api";
import type { PracticeSessionHistoryItem } from "../../features/practice/model/practice-types";
import { usePracticeSessionHistory } from "../../features/practice/model/usePracticeSessionHistory";
import { formatNumber, useLocale, type AppLocale } from "../../i18n";
import styles from "./SessionHistoryPage.module.css";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type SessionItemResult = "correct" | "wrong" | "skipped" | "pending";

function BackGlyph() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.9"
      viewBox="0 0 24 24"
    >
      <path d="m14.5 5-7 7 7 7M8 12h10" />
    </svg>
  );
}

function FlowGlyph() {
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
      <path d="M5 12h13M14 8l4 4-4 4" />
    </svg>
  );
}

function ResultGlyph({ result }: { result: SessionItemResult }) {
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
      {result === "correct" ? (
        <path d="m5 12.5 4.2 4.2L19 7" />
      ) : result === "wrong" || result === "skipped" ? (
        <path d="m7 7 10 10M17 7 7 17" />
      ) : (
        <>
          <circle cx="12" cy="12" r="7.5" />
          <path d="M12 8.2v4.3l2.7 1.7" />
        </>
      )}
    </svg>
  );
}

function HistoryGlyph() {
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
      <path d="M5.2 8.5A7.5 7.5 0 1 1 4.7 14" />
      <path d="M5.2 4.5v4h4M12 8.2v4.2l2.8 1.7" />
    </svg>
  );
}

function getItemResult(item: PracticeSessionHistoryItem): SessionItemResult {
  if (!item.isAnswered) {
    return "pending";
  }
  if (item.userTypedText === null) {
    return "skipped";
  }

  return item.isCorrect ? "correct" : "wrong";
}

function getResultLabel(result: SessionItemResult): string {
  if (result === "correct") {
    return "Верно";
  }
  if (result === "wrong") {
    return "Ошибка";
  }
  if (result === "skipped") {
    return "Пропущено";
  }

  return "Не отвечено";
}

function formatLanguage(language: string, locale: AppLocale): string {
  return language.trim().toLocaleUpperCase(locale);
}

function SessionAnswer({
  item,
  result,
}: {
  item: PracticeSessionHistoryItem;
  result: SessionItemResult;
}) {
  if (result === "pending") {
    return <strong className={styles.pendingAnswer}>Не отвечено</strong>;
  }

  if (result === "correct") {
    return (
      <strong className={styles.correctAnswer} lang={item.answerLanguage}>
        {item.userTypedText}
      </strong>
    );
  }

  if (result === "skipped") {
    return (
      <div className={styles.responseStack}>
        <span className={`${styles.responseLine} ${styles.responseSkipped}`}>
          <small>Пропущено</small>
        </span>
        <span className={`${styles.responseLine} ${styles.responseCorrect}`}>
          <small>Правильно</small>
          <strong lang={item.answerLanguage}>{item.answerText}</strong>
        </span>
      </div>
    );
  }

  return (
    <div className={styles.responseStack}>
      <span className={`${styles.responseLine} ${styles.responseWrong}`}>
        <small>Ваш ответ</small>
        <strong lang={item.answerLanguage}>{item.userTypedText}</strong>
      </span>
      <span className={`${styles.responseLine} ${styles.responseCorrect}`}>
        <small>Правильно</small>
        <strong lang={item.answerLanguage}>{item.answerText}</strong>
      </span>
    </div>
  );
}

function SessionHistoryItemCard({
  item,
  locale,
}: {
  item: PracticeSessionHistoryItem;
  locale: AppLocale;
}) {
  const result = getItemResult(item);
  const resultLabel = getResultLabel(result);

  return (
    <li className={styles.card} data-result={result}>
      <span aria-label={`Карточка ${item.sequenceNumber}`} className={styles.sequence}>
        {String(item.sequenceNumber).padStart(2, "0")}
      </span>

      <div className={styles.pair}>
        <div className={styles.term}>
          <span>{formatLanguage(item.promptLanguage, locale)}</span>
          <strong lang={item.promptLanguage}>{item.promptText}</strong>
        </div>

        <span className={styles.flow}>
          <FlowGlyph />
        </span>

        <div className={`${styles.term} ${styles.answer}`}>
          <span>{formatLanguage(item.answerLanguage, locale)}</span>
          <SessionAnswer item={item} result={result} />
        </div>
      </div>

      <span aria-label={resultLabel} className={styles.result} title={resultLabel}>
        <ResultGlyph result={result} />
      </span>
    </li>
  );
}

function SessionSummary({
  items,
  locale,
}: {
  items: readonly PracticeSessionHistoryItem[];
  locale: AppLocale;
}) {
  const correctCount = items.filter((item) => item.isCorrect === true).length;
  const wrongCount = items.filter(
    (item) => item.isAnswered && item.userTypedText !== null && item.isCorrect === false,
  ).length;
  const skippedCount = items.filter(
    (item) => item.isAnswered && item.userTypedText === null,
  ).length;
  const pendingCount = items.length - correctCount - wrongCount - skippedCount;

  return (
    <div aria-label="Итоги сессии" className={styles.summary}>
      <span aria-label={`Верно: ${correctCount}`} className={styles.summaryCorrect}>
        <ResultGlyph result="correct" />
        {formatNumber(correctCount, locale)}
      </span>
      <span aria-label={`Ошибки: ${wrongCount}`} className={styles.summaryWrong}>
        <ResultGlyph result="wrong" />
        {formatNumber(wrongCount, locale)}
      </span>
      {skippedCount > 0 ? (
        <span aria-label={`Пропущено: ${skippedCount}`} className={styles.summarySkipped}>
          <ResultGlyph result="skipped" />
          {formatNumber(skippedCount, locale)}
        </span>
      ) : null}
      {pendingCount > 0 ? (
        <span aria-label={`Не отвечено: ${pendingCount}`} className={styles.summaryPending}>
          <ResultGlyph result="pending" />
          {formatNumber(pendingCount, locale)}
        </span>
      ) : null}
    </div>
  );
}

function getHistoryErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "Не удалось загрузить историю.";
  }
  if (error.status === 403 || error.status === 404) {
    return "Сессия не найдена или больше недоступна.";
  }
  if (error.code === "INVALID_PRACTICE_RESPONSE") {
    return "Сервер вернул историю в неожиданном формате.";
  }
  if (error.status === 0) {
    return "Проверьте подключение и попробуйте снова.";
  }
  if (error.status >= 500) {
    return "Сервер временно недоступен.";
  }

  return "Не удалось загрузить историю.";
}

export function SessionHistoryPage() {
  const { session_uuid: sessionUuidParam } = useParams<{ session_uuid: string }>();
  const { locale } = useLocale();
  const sessionUuid =
    sessionUuidParam !== undefined && UUID_PATTERN.test(sessionUuidParam)
      ? sessionUuidParam.toLowerCase()
      : null;
  const history = usePracticeSessionHistory(sessionUuid);
  const readyItems = history.state.status === "ready" ? history.state.items : null;

  let content;
  if (sessionUuid === null) {
    content = (
      <div className={styles.message} role="alert">
        <HistoryGlyph />
        <strong>Некорректная ссылка</strong>
        <Link to="/practice">К сессиям</Link>
      </div>
    );
  } else if (history.state.status === "error") {
    content = (
      <div className={styles.message} role="alert">
        <HistoryGlyph />
        <strong>{getHistoryErrorMessage(history.state.error)}</strong>
        <button onClick={history.retry} type="button">
          Повторить
        </button>
      </div>
    );
  } else if (readyItems === null) {
    content = (
      <div aria-label="Загружаем историю сессии" className={styles.skeletons} role="status">
        <span />
        <span />
        <span />
        <span />
      </div>
    );
  } else if (readyItems.length === 0) {
    content = (
      <div className={styles.message}>
        <HistoryGlyph />
        <strong>История пуста</strong>
        <Link to="/practice">К сессиям</Link>
      </div>
    );
  } else {
    content = (
      <ol aria-label="Карточки тренировочной сессии" className={styles.cards}>
        {readyItems.map((item) => (
          <SessionHistoryItemCard item={item} key={item.itemUuid} locale={locale} />
        ))}
      </ol>
    );
  }

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <header className={styles.header}>
          <Link aria-label="Назад к тренировочным сессиям" className={styles.back} to="/practice">
            <BackGlyph />
          </Link>
          <div>
            <span>Практика</span>
            <h1>История сессии</h1>
          </div>
          {readyItems !== null && readyItems.length > 0 ? (
            <SessionSummary items={readyItems} locale={locale} />
          ) : null}
        </header>

        {content}
      </main>
    </div>
  );
}

export default SessionHistoryPage;
