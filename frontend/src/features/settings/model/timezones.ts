/** Пояс по умолчанию: его же ставит backend, если при регистрации пояс не пришёл. */
export const DEFAULT_TIMEZONE = "UTC";

/** IANA-зона браузера; `null`, если браузер её не сообщает. */
export function detectBrowserTimezone(): string | null {
  try {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return typeof timezone === "string" && timezone.length > 0 ? timezone : null;
  } catch {
    return null;
  }
}

function getSupportedTimezones(): readonly string[] {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return [];
  }
}

export interface TimezoneOption {
  value: string;
  /** Смещение в момент `at`, например «UTC+03:00»; `null`, если браузер не знает зону. */
  offset: string | null;
}

const OFFSET_PATTERN = /^UTC([+-])(\d{2}):(\d{2})$/;

function offsetToMinutes(offset: string | null): number | null {
  const match = offset === null ? null : OFFSET_PATTERN.exec(offset);
  if (match === null) {
    return null;
  }
  const minutes = Number(match[2]) * 60 + Number(match[3]);
  return match[1] === "-" ? -minutes : minutes;
}

/**
 * Варианты выбора пояса от UTC−12 к UTC+14 по смещению в момент `at`, при равном смещении
 * сначала UTC, затем по имени. Зоны с неизвестным смещением — в конце. UTC и текущее значение
 * есть всегда: браузер может не знать UTC в своём списке или знать сохранённую зону
 * под другим именем.
 */
export function getTimezoneOptions(current: string, at: Date): readonly TimezoneOption[] {
  const values = new Set(getSupportedTimezones());
  values.add(DEFAULT_TIMEZONE);
  values.add(current);

  const options = [...values].map((value) => {
    const offset = formatTimezoneOffset(value, at);
    return { value, offset, minutes: offsetToMinutes(offset) };
  });
  options.sort((left, right) => {
    if (left.minutes !== right.minutes) {
      if (left.minutes === null) return 1;
      if (right.minutes === null) return -1;
      return left.minutes - right.minutes;
    }
    if (left.value === DEFAULT_TIMEZONE) return -1;
    if (right.value === DEFAULT_TIMEZONE) return 1;
    return left.value.localeCompare(right.value);
  });
  return options.map(({ value, offset }) => ({ value, offset }));
}

/** Смещение зоны относительно UTC в момент `at`, например «UTC+03:00». */
export function formatTimezoneOffset(timezone: string, at: Date): string | null {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: timezone,
      timeZoneName: "longOffset",
    }).formatToParts(at);
    const name = parts.find((part) => part.type === "timeZoneName")?.value;
    if (name === undefined) {
      return null;
    }
    // "GMT" без смещения означает сам UTC
    return name === "GMT" ? "UTC+00:00" : name.replace("GMT", "UTC");
  } catch {
    return null;
  }
}
