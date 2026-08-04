import { Suspense, useEffect, type ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../layout/AppShell";
import { PageLoader } from "../PageLoader";
import { RouteGuard } from "./RouteGuard";
import { appRoutes } from "./route-config";

function RouteDocumentTitle({ children, title }: { children: ReactNode; title: string }) {
  useEffect(() => {
    document.title = title;
  }, [title]);

  return children;
}

function AppRoutes() {
  const protectedRoutes = appRoutes.filter(({ access }) => access === "protected");
  const standaloneRoutes = appRoutes.filter(({ access }) => access !== "protected");

  return (
    <Routes>
      <Route
        element={
          <RouteGuard access="protected">
            <AppShell />
          </RouteGuard>
        }
      >
        {protectedRoutes.map(({ Component, path, title }) => (
          <Route
            element={
              <RouteDocumentTitle title={title}>
                <Component />
              </RouteDocumentTitle>
            }
            key={path}
            path={path}
          />
        ))}
      </Route>

      {standaloneRoutes.map(({ Component, access, path, title }) => (
        <Route
          element={
            <RouteGuard access={access}>
              <RouteDocumentTitle title={title}>
                <Suspense fallback={<PageLoader tone="dark" />}>
                  <Component />
                </Suspense>
              </RouteDocumentTitle>
            </RouteGuard>
          }
          key={path}
          path={path}
        />
      ))}
    </Routes>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
