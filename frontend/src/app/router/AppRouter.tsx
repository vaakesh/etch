import { Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { RouteGuard } from "./RouteGuard";
import { appRoutes } from "./route-config";

function AppRoutes() {
  return (
    <Routes>
      {appRoutes.map(({ Component, access, path }) => (
        <Route
          element={
            <RouteGuard access={access}>
              <Suspense fallback={<div aria-label="Загрузка страницы" role="status" />}>
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
