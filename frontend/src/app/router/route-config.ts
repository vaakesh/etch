import { lazy, type ComponentType, type LazyExoticComponent } from "react";
import { DECK_DETAILS_ROUTE_PATH } from "../../features/decks/model/deck-details-navigation";
import type { AppLocale } from "../../i18n";

export type RouteAccess = "public" | "protected" | "guest";

export interface AppRouteDefinition {
  path: string;
  access: RouteAccess;
  title: Readonly<Record<AppLocale, string>>;
  Component: LazyExoticComponent<ComponentType>;
}

const LoginPage = lazy(() => import("../../pages/LoginPage"));
const HomePage = lazy(() => import("../../pages/HomePage"));
const LibraryPage = lazy(() => import("../../pages/LibraryPage"));
const LibraryArchivePage = lazy(() => import("../../pages/LibraryArchivePage"));
const DeckDetailsPage = lazy(() => import("../../pages/DeckDetailsPage"));
const CatalogPage = lazy(() => import("../../pages/CatalogPage"));
const UserProfilePage = lazy(() => import("../../pages/UserProfilePage"));
const LibraryDeckEditPage = lazy(() => import("../../pages/LibraryDeckEditPage"));
const PracticePage = lazy(() => import("../../pages/PracticePage"));
const SessionHistoryPage = lazy(() => import("../../pages/SessionHistoryPage"));
const SettingsPage = lazy(() => import("../../pages/SettingsPage"));
const NotFoundPage = lazy(() => import("../../pages/NotFoundPage"));

export const appRoutes: readonly AppRouteDefinition[] = [
  {
    path: "/login",
    access: "guest",
    title: { "ru-RU": "Вход — Etch", "en-US": "Sign in — Etch" },
    Component: LoginPage,
  },
  {
    path: "/",
    access: "protected",
    title: { "ru-RU": "Главная — Etch", "en-US": "Home — Etch" },
    Component: HomePage,
  },
  {
    path: "/library",
    access: "protected",
    title: { "ru-RU": "Библиотека — Etch", "en-US": "Library — Etch" },
    Component: LibraryPage,
  },
  {
    path: "/library/decks",
    access: "protected",
    title: { "ru-RU": "Колоды — Etch", "en-US": "Decks — Etch" },
    Component: LibraryPage,
  },
  {
    path: "/library/cards",
    access: "protected",
    title: { "ru-RU": "Карточки — Etch", "en-US": "Cards — Etch" },
    Component: LibraryPage,
  },
  {
    path: "/library/decks/archive",
    access: "protected",
    title: { "ru-RU": "Архив колод — Etch", "en-US": "Deck archive — Etch" },
    Component: LibraryArchivePage,
  },
  {
    path: DECK_DETAILS_ROUTE_PATH,
    access: "protected",
    title: { "ru-RU": "Колода — Etch", "en-US": "Deck — Etch" },
    Component: DeckDetailsPage,
  },
  {
    path: "/catalog",
    access: "protected",
    title: { "ru-RU": "Каталог — Etch", "en-US": "Catalog — Etch" },
    Component: CatalogPage,
  },
  {
    path: "/users/:username",
    access: "protected",
    title: { "ru-RU": "Профиль — Etch", "en-US": "Profile — Etch" },
    Component: UserProfilePage,
  },
  {
    path: "/library/:deck_uuid/edit",
    access: "protected",
    title: { "ru-RU": "Редактор колоды — Etch", "en-US": "Deck editor — Etch" },
    Component: LibraryDeckEditPage,
  },
  {
    path: "/practice",
    access: "protected",
    title: { "ru-RU": "Практика — Etch", "en-US": "Practice — Etch" },
    Component: PracticePage,
  },
  {
    path: "/practice/sessions/:session_uuid/history",
    access: "protected",
    title: { "ru-RU": "История сессии — Etch", "en-US": "Session history — Etch" },
    Component: SessionHistoryPage,
  },
  {
    path: "/settings",
    access: "protected",
    title: { "ru-RU": "Настройки — Etch", "en-US": "Settings — Etch" },
    Component: SettingsPage,
  },
  {
    path: "*",
    access: "public",
    title: { "ru-RU": "Страница не найдена — Etch", "en-US": "Page not found — Etch" },
    Component: NotFoundPage,
  },
];
