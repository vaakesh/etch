import type { AppLocale } from "./localization";

type MessageShape<T> = T extends (...args: infer Arguments) => string
  ? (...args: Arguments) => string
  : T extends string
    ? string
    : T extends Readonly<Record<string, unknown>>
      ? { readonly [Key in keyof T]: MessageShape<T[Key]> }
      : never;

export type LocalizedMessages<T> = Readonly<Record<AppLocale, MessageShape<T>>>;

export function defineMessages<const T extends Readonly<Record<string, unknown>>>(
  russian: T,
  english: MessageShape<T>,
): LocalizedMessages<T> {
  return {
    "ru-RU": russian,
    "en-US": english,
  } as LocalizedMessages<T>;
}
