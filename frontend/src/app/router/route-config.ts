import type { ComponentType, LazyExoticComponent } from "react";

export type RouteAccess = "public" | "protected" | "guest";

export interface AppRouteDefinition {
  path: string;
  access: RouteAccess;
  Component: LazyExoticComponent<ComponentType>;
}

export const appRoutes: readonly AppRouteDefinition[] = [];
