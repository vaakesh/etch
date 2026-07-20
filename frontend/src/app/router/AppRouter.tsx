import { Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../layout/AppShell";
import { PageLoader } from "../PageLoader";
import { RouteGuard } from "./RouteGuard";
import { appRoutes } from "./route-config";

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
        {protectedRoutes.map(({ Component, path }) => (
          <Route element={<Component />} key={path} path={path} />
        ))}
      </Route>

      {standaloneRoutes.map(({ Component, access, path }) => (
        <Route
          element={
            <RouteGuard access={access}>
              <Suspense fallback={<PageLoader tone="dark" />}>
                <Component />
              </Suspense>
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
