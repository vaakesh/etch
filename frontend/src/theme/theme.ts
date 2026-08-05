export const APP_THEMES = ["light", "dark", "system"] as const;

export type AppTheme = (typeof APP_THEMES)[number];
export type ResolvedTheme = Exclude<AppTheme, "system">;

export const DEFAULT_THEME: AppTheme = "system";

export function isAppTheme(value: unknown): value is AppTheme {
  return typeof value === "string" && APP_THEMES.some((theme) => theme === value);
}

export function resolveTheme(theme: AppTheme, prefersDark: boolean): ResolvedTheme {
  if (theme === "system") {
    return prefersDark ? "dark" : "light";
  }

  return theme;
}
