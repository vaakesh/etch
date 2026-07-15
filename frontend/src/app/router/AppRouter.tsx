import { Suspense } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { PageLoader } from "../PageLoader";
import { RouteGuard } from "./RouteGuard";
import { appRoutes } from "./route-config";

function AppRoutes() {
  const location = useLocation();

  return (
    <Routes>
      {appRoutes.map(({ Component, access, path }) => (
        <Route
          element={
            <RouteGuard access={access} key={`${path}:${location.key}`}>
              <Suspense fallback={<PageLoader />}>
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
