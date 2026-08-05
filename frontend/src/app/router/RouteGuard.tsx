import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/hooks/useAuth";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import { PageLoader } from "../PageLoader";
import {
  getSafeReturnPath,
  HOME_PATH,
  LOGIN_PATH,
  SESSION_EXPIRED_NOTICE,
} from "./navigation-state";
import type { RouteAccess } from "./route-config";
import styles from "./RouteGuard.module.css";

interface RouteGuardProps {
  access: RouteAccess;
  children: ReactNode;
}

const MESSAGES = defineMessages(
  {
    eyebrow: "Etch · соединение",
    title: "Не удалось проверить сессию",
    description: "Сервер временно недоступен. Проверьте подключение и попробуйте ещё раз.",
    retry: "Повторить",
  },
  {
    eyebrow: "Etch · connection",
    title: "We couldn't verify your session",
    description: "The server is temporarily unavailable. Check your connection and try again.",
    retry: "Try again",
  },
);

export function RouteGuard({ access, children }: RouteGuardProps) {
  const messages = useLocalizedMessages(MESSAGES);
  const { initialize, status } = useAuth();
  const location = useLocation();
  const [isSessionRevalidated, setIsSessionRevalidated] = useState(access !== "protected");

  useEffect(() => {
    if (access !== "protected") {
      return;
    }

    let isActive = true;

    void initialize().finally(() => {
      if (isActive) {
        setIsSessionRevalidated(true);
      }
    });

    return () => {
      isActive = false;
    };
  }, [access, initialize]);

  if (access === "public") {
    return children;
  }

  if (!isSessionRevalidated || status === "loading") {
    return <PageLoader tone={access === "protected" ? "light" : "dark"} />;
  }

  if (status === "error") {
    return (
      <main className={styles.page}>
        <div aria-hidden="true" className={styles.ambient}>
          <span className={styles.ambientOrb} />
          <span className={styles.ambientLetter}>Aa</span>
        </div>
        <section aria-labelledby="session-error-title" className={styles.card} role="alert">
          <div aria-hidden="true" className={styles.visual}>
            <span className={styles.visualCardBack} />
            <span className={styles.visualCardFront}>?</span>
          </div>
          <div className={styles.copy}>
            <span aria-hidden="true" className={styles.mark}>
              {messages.eyebrow}
            </span>
            <h1 id="session-error-title">{messages.title}</h1>
            <p>{messages.description}</p>
            <button onClick={() => void initialize()} type="button">
              {messages.retry}
              <span aria-hidden="true">↻</span>
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (access === "guest") {
    if (status === "authorized") {
      return <Navigate replace to={getSafeReturnPath(location.state, HOME_PATH)} />;
    }

    return children;
  }

  if (status === "authorized") {
    return children;
  }

  const requestedPath = `${location.pathname}${location.search}${location.hash}`;
  return (
    <Navigate
      replace
      state={{ from: requestedPath, notice: SESSION_EXPIRED_NOTICE }}
      to={LOGIN_PATH}
    />
  );
}
