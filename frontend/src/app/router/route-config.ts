import { lazy, type ComponentType, type LazyExoticComponent } from "react";

export type RouteAccess = "public" | "protected" | "guest";

export interface AppRouteDefinition {
  path: string;
  access: RouteAccess;
  title: string;
  Component: LazyExoticComponent<ComponentType>;
}

const LoginPage = lazy(() => import("../../pages/LoginPage"));
const HomePage = lazy(() => import("../../pages/HomePage"));
const LibraryPage = lazy(() => import("../../pages/LibraryPage"));
const LibraryDeckEditPage = lazy(() => import("../../pages/LibraryDeckEditPage"));
const PracticePage = lazy(() => import("../../pages/PracticePage"));
const SessionHistoryPage = lazy(() => import("../../pages/SessionHistoryPage"));
const NotFoundPage = lazy(() => import("../../pages/NotFoundPage"));

export const appRoutes: readonly AppRouteDefinition[] = [
  {
    path: "/login",
    access: "guest",
    title: "Вход — Etch",
    Component: LoginPage,
  },
  {
    path: "/",
    access: "protected",
    title: "Главная — Etch",
    Component: HomePage,
  },
  {
    path: "/library",
    access: "protected",
    title: "Библиотека — Etch",
    Component: LibraryPage,
  },
  {
    path: "/library/:deck_uuid/edit",
    access: "protected",
    title: "Редактор колоды — Etch",
    Component: LibraryDeckEditPage,
  },
  {
    path: "/practice",
    access: "protected",
    title: "Практика — Etch",
    Component: PracticePage,
  },
  {
    path: "/practice/sessions/:session_uuid/history",
    access: "protected",
    title: "История сессии — Etch",
    Component: SessionHistoryPage,
  },
  {
    path: "*",
    access: "public",
    title: "Страница не найдена — Etch",
    Component: NotFoundPage,
  },
];
