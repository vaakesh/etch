import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/hooks/useAuth";
import { DASHBOARD_PATH, getSafeReturnPath, LOGIN_PATH } from "./navigation-state";
import type { RouteAccess } from "./route-config";

interface RouteGuardProps {
  access: RouteAccess;
  children: ReactNode;
}

export function RouteGuard({ access, children }: RouteGuardProps) {
  const auth = useAuth();
  const location = useLocation();

  if (access === "public") {
    return children;
  }

  if (auth.status === "loading") {
    return (
      <div aria-live="polite" role="status">
        Проверяем сессию…
      </div>
    );
  }

  if (auth.status === "error") {
    return (
      <div role="alert">
        <p>Не удалось проверить сессию.</p>
        <button onClick={() => void auth.initialize()} type="button">
          Повторить
        </button>
      </div>
    );
  }

  if (access === "guest") {
    if (auth.status === "authorized") {
      return <Navigate replace to={getSafeReturnPath(location.state, DASHBOARD_PATH)} />;
    }

    return children;
  }

  if (auth.status === "authorized") {
    return children;
  }

  const requestedPath = `${location.pathname}${location.search}${location.hash}`;
  return <Navigate replace state={{ from: requestedPath }} to={LOGIN_PATH} />;
}
