import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/hooks/useAuth";
import { PageLoader } from "../PageLoader";
import { getSafeReturnPath, HOME_PATH, LOGIN_PATH } from "./navigation-state";
import type { RouteAccess } from "./route-config";

interface RouteGuardProps {
  access: RouteAccess;
  children: ReactNode;
}

export function RouteGuard({ access, children }: RouteGuardProps) {
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
    return <PageLoader />;
  }

  if (status === "error") {
    return (
      <div role="alert">
        <p>Не удалось проверить сессию.</p>
        <button onClick={() => void initialize()} type="button">
          Повторить
        </button>
      </div>
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
  return <Navigate replace state={{ from: requestedPath }} to={LOGIN_PATH} />;
}
