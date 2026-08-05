import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { isApiError } from "../../../api";
import { useAuth } from "../../../auth/hooks/useAuth";
import {
  DEFAULT_LOCALE,
  defineMessages,
  useLocalizedMessages,
  type AppLocale,
} from "../../../i18n";
import { DEFAULT_THEME, type AppTheme } from "../../../theme";
import { updateUserSettingsRequest } from "../api/settings-api";
import type { UserSettings } from "./settings-types";

export type SettingsMutationStatus = "idle" | "saving" | "success" | "error";

export interface UseUserSettingsResult {
  draft: UserSettings;
  errorMessage: string | null;
  isDirty: boolean;
  setLocale: (locale: AppLocale) => void;
  setTheme: (theme: AppTheme) => void;
  reset: () => void;
  save: () => Promise<void>;
  status: SettingsMutationStatus;
}

const FALLBACK_SETTINGS: UserSettings = {
  locale: DEFAULT_LOCALE,
  theme: DEFAULT_THEME,
};

const ERROR_MESSAGES = defineMessages(
  {
    generic: "Не удалось сохранить настройки. Попробуйте ещё раз.",
    invalidResponse: "Сервер сохранил настройки, но вернул данные в неожиданном формате.",
    forbidden: "У этой учётной записи нет доступа к изменению настроек.",
    notFound: "Настройки учётной записи не найдены на сервере.",
    validation: "Сервер не поддерживает выбранные значения локали или темы.",
    network: "Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.",
    server: "Сервер временно не может сохранить настройки. Попробуйте немного позже.",
  },
  {
    generic: "We couldn't save your settings. Try again.",
    invalidResponse: "The server saved your settings but returned an unexpected response.",
    forbidden: "This account does not have permission to change settings.",
    notFound: "The server could not find settings for this account.",
    validation: "The server does not support the selected locale or theme.",
    network: "We couldn't reach the server. Check your connection and try again.",
    server: "The server cannot save your settings right now. Try again later.",
  },
);

function getSettingsErrorMessage(
  error: unknown,
  messages: (typeof ERROR_MESSAGES)["ru-RU"],
): string {
  if (!isApiError(error)) {
    return messages.generic;
  }

  if (error.code === "INVALID_SETTINGS_RESPONSE") {
    return messages.invalidResponse;
  }
  if (error.status === 403) {
    return messages.forbidden;
  }
  if (error.status === 404) {
    return messages.notFound;
  }
  if (error.status === 422) {
    return messages.validation;
  }
  if (error.status === 0) {
    return messages.network;
  }
  if (error.status >= 500) {
    return messages.server;
  }

  return messages.generic;
}

export function useUserSettings(): UseUserSettingsResult {
  const messages = useLocalizedMessages(ERROR_MESSAGES);
  const { applyUserSettings, user } = useAuth();
  const savedSettings = user?.settings ?? FALLBACK_SETTINGS;
  const [draft, setDraft] = useState<UserSettings>(savedSettings);
  const [status, setStatus] = useState<SettingsMutationStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const operationRef = useRef(0);

  useEffect(
    () => () => {
      activeControllerRef.current?.abort("settings-page-unmounted");
    },
    [],
  );

  const updateDraft = useCallback((update: Partial<UserSettings>): void => {
    setDraft((current) => ({ ...current, ...update }));
    setStatus("idle");
    setErrorMessage(null);
  }, []);

  const setLocale = useCallback(
    (locale: AppLocale): void => updateDraft({ locale }),
    [updateDraft],
  );

  const setTheme = useCallback((theme: AppTheme): void => updateDraft({ theme }), [updateDraft]);

  const reset = useCallback((): void => {
    activeControllerRef.current?.abort("settings-reset");
    activeControllerRef.current = null;
    operationRef.current += 1;
    setDraft(savedSettings);
    setStatus("idle");
    setErrorMessage(null);
  }, [savedSettings]);

  const save = useCallback(async (): Promise<void> => {
    if (status === "saving") {
      return;
    }

    const controller = new AbortController();
    activeControllerRef.current?.abort("settings-save-superseded");
    activeControllerRef.current = controller;
    const operation = ++operationRef.current;

    setStatus("saving");
    setErrorMessage(null);

    try {
      const updatedSettings = await updateUserSettingsRequest(draft, controller.signal);
      if (controller.signal.aborted || operation !== operationRef.current) {
        return;
      }

      applyUserSettings(updatedSettings);
      setDraft(updatedSettings);
      setStatus("success");
    } catch (error) {
      if (controller.signal.aborted || operation !== operationRef.current) {
        return;
      }

      setErrorMessage(getSettingsErrorMessage(error, messages));
      setStatus("error");
    } finally {
      if (activeControllerRef.current === controller) {
        activeControllerRef.current = null;
      }
    }
  }, [applyUserSettings, draft, messages, status]);

  const isDirty = useMemo(
    () => draft.locale !== savedSettings.locale || draft.theme !== savedSettings.theme,
    [draft, savedSettings],
  );

  return {
    draft,
    errorMessage,
    isDirty,
    reset,
    save,
    setLocale,
    setTheme,
    status,
  };
}
