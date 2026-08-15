import { type FormEvent } from "react";
import { useUserSettings } from "../../features/settings/model/useUserSettings";
import {
  defineMessages,
  isSupportedLocale,
  useLocalizedMessages,
  type AppLocale,
} from "../../i18n";
import type { AppTheme } from "../../theme";
import styles from "./SettingsPage.module.css";

interface LocaleOption {
  value: AppLocale;
  label: string;
}

interface ThemeOption {
  value: AppTheme;
  label: string;
}

const MESSAGES = defineMessages(
  {
    title: "Настройки",
    language: "Язык",
    appearance: "Оформление",
    longTextPreviews: "Предпросмотр длинного текста",
    longTextPreviewsHint: "Показывать полный текст при наведении или фокусе",
    enabled: "Включено",
    disabled: "Выключено",
    themeNames: { light: "Светлая", dark: "Тёмная", system: "Системная" },
    success: "Сохранено",
    dirty: "Есть изменения",
    cancel: "Отменить",
    saving: "Сохраняем…",
    save: "Сохранить",
  },
  {
    title: "Settings",
    language: "Language",
    appearance: "Appearance",
    longTextPreviews: "Long text previews",
    longTextPreviewsHint: "Show the full text on hover or focus",
    enabled: "On",
    disabled: "Off",
    themeNames: { light: "Light", dark: "Dark", system: "System" },
    success: "Saved",
    dirty: "Unsaved changes",
    cancel: "Cancel",
    saving: "Saving…",
    save: "Save",
  },
);

const LOCALE_OPTIONS: readonly LocaleOption[] = [
  { value: "en-US", label: "en (English)" },
  { value: "ru-RU", label: "ru (Russian)" },
];

function SelectChevron() {
  return (
    <svg aria-hidden="true" className={styles.selectChevron} fill="none" viewBox="0 0 16 16">
      <path d="m4 6 4 4 4-4" />
    </svg>
  );
}

function LocalePicker({
  disabled,
  locale,
  onChange,
}: {
  disabled: boolean;
  locale: AppLocale;
  onChange: (locale: AppLocale) => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div className={styles.settingRow}>
      <label className={styles.settingLabel} htmlFor="settings-locale">
        {messages.language}
      </label>
      <span className={styles.selectControl}>
        <select
          disabled={disabled}
          id="settings-locale"
          name="locale"
          onChange={(event) => {
            const nextLocale = event.currentTarget.value;
            if (isSupportedLocale(nextLocale)) {
              onChange(nextLocale);
            }
          }}
          value={locale}
        >
          {LOCALE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <SelectChevron />
      </span>
    </div>
  );
}

function ThemePicker({
  disabled,
  onChange,
  theme,
}: {
  disabled: boolean;
  onChange: (theme: AppTheme) => void;
  theme: AppTheme;
}) {
  const messages = useLocalizedMessages(MESSAGES);
  const themeOptions: readonly ThemeOption[] = [
    { value: "light", label: messages.themeNames.light },
    { value: "dark", label: messages.themeNames.dark },
    { value: "system", label: messages.themeNames.system },
  ];

  return (
    <div className={styles.settingRow}>
      <span className={styles.settingLabel} id="settings-theme-label">
        {messages.appearance}
      </span>
      <div
        aria-labelledby="settings-theme-label"
        aria-disabled={disabled}
        className={styles.themeSwitch}
        data-active-theme={theme}
        role="radiogroup"
      >
        {themeOptions.map((option) => (
          <label className={styles.themeOption} key={option.value}>
            <input
              checked={theme === option.value}
              disabled={disabled}
              name="theme"
              onChange={() => onChange(option.value)}
              type="radio"
              value={option.value}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function LongTextPreviewToggle({
  disabled,
  enabled,
  onChange,
}: {
  disabled: boolean;
  enabled: boolean;
  onChange: (enabled: boolean) => void;
}) {
  const messages = useLocalizedMessages(MESSAGES);

  return (
    <div className={styles.settingRow}>
      <span className={styles.settingCopy}>
        <span className={styles.settingLabel} id="settings-long-text-previews-label">
          {messages.longTextPreviews}
        </span>
        <span className={styles.settingHint} id="settings-long-text-previews-hint">
          {messages.longTextPreviewsHint}
        </span>
      </span>
      <label className={styles.previewToggle}>
        <input
          aria-describedby="settings-long-text-previews-hint"
          aria-labelledby="settings-long-text-previews-label"
          checked={enabled}
          disabled={disabled}
          name="show_previews_for_long"
          onChange={(event) => onChange(event.currentTarget.checked)}
          type="checkbox"
        />
        <span aria-hidden="true" className={styles.previewToggleTrack} />
        <span aria-hidden="true" className={styles.previewToggleState}>
          {enabled ? messages.enabled : messages.disabled}
        </span>
      </label>
    </div>
  );
}

export function SettingsPage() {
  const messages = useLocalizedMessages(MESSAGES);
  const {
    draft,
    errorMessage,
    isDirty,
    reset,
    save,
    setLocale,
    setShowPreviewsForLong,
    setTheme,
    status,
  } = useUserSettings();
  const isSaving = status === "saving";

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void save();
  }

  return (
    <main className={styles.page}>
      <div className={styles.content}>
        <header className={styles.header}>
          <h1>{messages.title}</h1>
        </header>

        <form aria-busy={isSaving} className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.settingsList}>
            <LocalePicker disabled={isSaving} locale={draft.locale} onChange={setLocale} />
            <ThemePicker disabled={isSaving} onChange={setTheme} theme={draft.theme} />
            <LongTextPreviewToggle
              disabled={isSaving}
              enabled={draft.showPreviewsForLong}
              onChange={setShowPreviewsForLong}
            />
          </div>

          <footer className={styles.formFooter}>
            <div aria-live="polite" className={styles.status}>
              {status === "success" ? (
                <span className={styles.successMessage} role="status">
                  {messages.success}
                </span>
              ) : null}
              {status === "error" && errorMessage ? (
                <span className={styles.errorMessage} role="alert">
                  {errorMessage}
                </span>
              ) : null}
              {status === "idle" && isDirty ? <span>{messages.dirty}</span> : null}
            </div>

            <div className={styles.actions}>
              <button
                className={styles.resetButton}
                disabled={!isDirty || isSaving}
                onClick={reset}
                type="button"
              >
                {messages.cancel}
              </button>
              <button className={styles.saveButton} disabled={!isDirty || isSaving} type="submit">
                {isSaving ? <span aria-hidden="true" className={styles.spinner} /> : null}
                {isSaving ? messages.saving : messages.save}
              </button>
            </div>
          </footer>
        </form>
      </div>
    </main>
  );
}

export default SettingsPage;
