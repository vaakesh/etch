import { lazy, type ComponentType, type LazyExoticComponent } from "react";

export type RouteAccess = "public" | "protected" | "guest";

export interface AppRouteDefinition {
  path: string;
  access: RouteAccess;
  Component: LazyExoticComponent<ComponentType>;
}

const LoginPage = lazy(() => import("../../pages/LoginPage"));
const HomePage = lazy(() => import("../../pages/HomePage"));
const NotFoundPage = lazy(() => import("../../pages/NotFoundPage"));

export const appRoutes: readonly AppRouteDefinition[] = [
  {
    path: "/login",
    access: "guest",
    Component: LoginPage,
  },
  {
    path: "/",
    access: "protected",
    Component: HomePage,
  },
  {
    path: "*",
    access: "public",
    Component: NotFoundPage,
  },
];
