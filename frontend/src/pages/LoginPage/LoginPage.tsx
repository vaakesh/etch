import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type AnimationEvent as ReactAnimationEvent,
  type FormEvent,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { API_ERROR_CODES, hasApiErrorCode, isApiError } from "../../api";
import {
  hasSessionExpiredNotice,
  withoutSessionExpiredNotice,
} from "../../app/router/navigation-state";
import { registerRequest } from "../../auth/api/auth-api";
import { useAuth } from "../../auth/hooks/useAuth";
import { defineMessages, useLocalizedMessages } from "../../i18n";
import styles from "./LoginPage.module.css";

const INVALID_CREDENTIALS_STATUSES = new Set([401, 403, 404]);
const USERNAME_MIN_LENGTH = 3;
const USERNAME_MAX_LENGTH = 18;
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_LENGTH = 128;

type AuthMode = "login" | "register";

interface FormError {
  invalidFields: boolean;
  message: string;
}

const MESSAGES = defineMessages(
  {
    invalidCredentials: "Неверное имя пользователя или пароль.",
    invalidFormat:
      "Имя пользователя — 3–18 символов без пробелов, пароль — 8–128 символов без пробелов.",
    registrationConflict: "Пользователь с таким именем или email уже существует.",
    registrationInvalidFormat:
      "Проверьте поля: имя пользователя — 3–18 символов без пробелов, пароль — 8–128 символов без пробелов, email должен быть корректным.",
    networkError: "Не удалось связаться с сервером. Попробуйте ещё раз.",
    genericError: "Не удалось войти. Попробуйте ещё раз.",
    registrationError: "Не удалось создать аккаунт. Попробуйте ещё раз.",
    registrationLoginFailed: "Аккаунт создан, но войти автоматически не удалось. Попробуйте войти.",
    usernameRequired: "Введите имя пользователя.",
    emailRequired: "Введите email.",
    cardFront: "hello",
    cardBack: "привет",
    visualLabel: "Ваш словарь",
    visualTitle: "Слова, которые остаются с вами.",
    loginMode: "Вход",
    registerMode: "Регистрация",
    modeLabel: "Выберите действие",
    loginEyebrow: "Личный кабинет",
    loginTitle: "С возвращением",
    loginLead: "Продолжите учиться с того места, где остановились.",
    registerEyebrow: "Новый аккаунт",
    registerTitle: "Начните с Etch",
    registerLead: "Создайте аккаунт, чтобы собирать свой словарь и запоминать больше.",
    expired: "Сессия истекла. Войдите снова.",
    username: "Имя пользователя",
    usernameHint: "3–18 символов, без пробелов.",
    email: "Email",
    password: "Пароль",
    passwordHint: "8–128 символов, без пробелов.",
    loginSubmitting: "Входим…",
    loginSubmit: "Войти",
    registerSubmitting: "Создаём аккаунт…",
    registerSubmit: "Создать аккаунт",
  },
  {
    invalidCredentials: "Incorrect username or password.",
    invalidFormat:
      "Username must be 3–18 characters without spaces; password must be 8–128 characters without spaces.",
    registrationConflict: "An account with this username or email already exists.",
    registrationInvalidFormat:
      "Check the fields: username must be 3–18 characters without spaces, password must be 8–128 characters without spaces, and email must be valid.",
    networkError: "We couldn't reach the server. Try again.",
    genericError: "We couldn't sign you in. Try again.",
    registrationError: "We couldn't create your account. Try again.",
    registrationLoginFailed:
      "Your account was created, but automatic sign-in failed. Try signing in.",
    usernameRequired: "Enter your username.",
    emailRequired: "Enter your email.",
    cardFront: "hello",
    cardBack: "hi",
    visualLabel: "Your vocabulary",
    visualTitle: "Words that stay with you.",
    loginMode: "Sign in",
    registerMode: "Register",
    modeLabel: "Choose an action",
    loginEyebrow: "Your account",
    loginTitle: "Welcome back",
    loginLead: "Continue learning right where you left off.",
    registerEyebrow: "New account",
    registerTitle: "Start with Etch",
    registerLead: "Create an account to build your vocabulary and remember more.",
    expired: "Your session expired. Sign in again.",
    username: "Username",
    usernameHint: "3–18 characters, no spaces.",
    email: "Email",
    password: "Password",
    passwordHint: "8–128 characters, no spaces.",
    loginSubmitting: "Signing in…",
    loginSubmit: "Sign in",
    registerSubmitting: "Creating account…",
    registerSubmit: "Create account",
  },
);

function getLoginError(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): FormError {
  if (isApiError(error)) {
    if (
      hasApiErrorCode(error, API_ERROR_CODES.invalidLoginCredentials) ||
      INVALID_CREDENTIALS_STATUSES.has(error.status)
    ) {
      return { invalidFields: true, message: messages.invalidCredentials };
    }

    if (error.status === 422) {
      return { invalidFields: true, message: messages.invalidFormat };
    }

    if (error.status === 0) {
      return { invalidFields: false, message: messages.networkError };
    }
  }

  return { invalidFields: false, message: messages.genericError };
}

function getRegistrationError(error: unknown, messages: (typeof MESSAGES)["ru-RU"]): FormError {
  if (isApiError(error)) {
    if (hasApiErrorCode(error, API_ERROR_CODES.userAlreadyExists) || error.status === 409) {
      return { invalidFields: true, message: messages.registrationConflict };
    }

    if (error.status === 422) {
      return { invalidFields: true, message: messages.registrationInvalidFormat };
    }

    if (error.status === 0) {
      return { invalidFields: false, message: messages.networkError };
    }
  }

  return { invalidFields: false, message: messages.registrationError };
}

function joinDescriptionIds(...ids: Array<string | undefined>): string | undefined {
  const description = ids.filter((id): id is string => Boolean(id)).join(" ");
  return description || undefined;
}

function getInitialAuthMode(search: string): AuthMode {
  return new URLSearchParams(search).get("mode") === "register" ? "register" : "login";
}

export function LoginPage() {
  const messages = useLocalizedMessages(MESSAGES);
  const { login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>(() => getInitialAuthMode(location.search));
  const [showSessionExpiredNotice] = useState(() => hasSessionExpiredNotice(location.state));
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<FormError | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAcceptingInput, setIsAcceptingInput] = useState(false);
  const formRef = useRef<HTMLFormElement | null>(null);
  const usernameInputRef = useRef<HTMLInputElement | null>(null);
  const emailInputRef = useRef<HTMLInputElement | null>(null);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const submitControllerRef = useRef<AbortController | null>(null);

  const clearRenderedFields = useCallback((): void => {
    formRef.current?.reset();

    if (usernameInputRef.current) {
      usernameInputRef.current.value = "";
    }
    if (emailInputRef.current) {
      emailInputRef.current.value = "";
    }
    if (passwordInputRef.current) {
      passwordInputRef.current.value = "";
    }
  }, []);

  const clearForm = useCallback((): void => {
    setUsername("");
    setEmail("");
    setPassword("");
    setFormError(null);
    setIsSubmitting(false);
    setIsAcceptingInput(false);
    clearRenderedFields();
  }, [clearRenderedFields]);

  const enableFormInput = useCallback((): void => {
    if (isAcceptingInput) {
      return;
    }

    if (mode === "register") {
      setIsAcceptingInput(true);
      return;
    }

    clearForm();
    setIsAcceptingInput(true);
  }, [clearForm, isAcceptingInput, mode]);

  const handleAutofillDetected = useCallback(
    (event: ReactAnimationEvent<HTMLInputElement>): void => {
      if (isAcceptingInput || mode === "register") {
        return;
      }

      event.currentTarget.value = "";
      if (event.currentTarget === usernameInputRef.current) {
        setUsername("");
      }
      if (event.currentTarget === emailInputRef.current) {
        setEmail("");
      }
      if (event.currentTarget === passwordInputRef.current) {
        setPassword("");
      }
    },
    [isAcceptingInput, mode],
  );

  useEffect(() => {
    if (!hasSessionExpiredNotice(location.state)) {
      return;
    }

    void navigate(`${location.pathname}${location.search}${location.hash}`, {
      replace: true,
      state: withoutSessionExpiredNotice(location.state),
    });
  }, [location.hash, location.pathname, location.search, location.state, navigate]);

  useEffect(() => {
    clearRenderedFields();

    const handlePageHide = (): void => {
      submitControllerRef.current?.abort();
      submitControllerRef.current = null;
      clearForm();
    };
    const handlePageShow = (): void => {
      clearForm();
    };

    window.addEventListener("pagehide", handlePageHide);
    window.addEventListener("pageshow", handlePageShow);

    return () => {
      window.removeEventListener("pagehide", handlePageHide);
      window.removeEventListener("pageshow", handlePageShow);
      submitControllerRef.current?.abort();
      submitControllerRef.current = null;
      clearRenderedFields();
    };
  }, [clearForm, clearRenderedFields]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      setFormError({ invalidFields: true, message: messages.usernameRequired });
      return;
    }

    const normalizedEmail = email.trim();
    if (mode === "register" && !normalizedEmail) {
      setFormError({ invalidFields: true, message: messages.emailRequired });
      return;
    }

    const controller = new AbortController();
    submitControllerRef.current?.abort();
    submitControllerRef.current = controller;
    setFormError(null);
    setIsSubmitting(true);
    let accountCreated = false;

    try {
      if (mode === "register") {
        await registerRequest(
          {
            username: normalizedUsername,
            email: normalizedEmail,
            password,
          },
          controller.signal,
        );
        accountCreated = true;
      }

      await login({ username: normalizedUsername, password }, controller.signal);
      if (!controller.signal.aborted) {
        setUsername("");
        setEmail("");
        setPassword("");
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        if (accountCreated) {
          setMode("login");
          setEmail("");
          setFormError({ invalidFields: false, message: messages.registrationLoginFailed });
        } else {
          setFormError(
            mode === "register"
              ? getRegistrationError(error, messages)
              : getLoginError(error, messages),
          );
        }
      }
    } finally {
      if (submitControllerRef.current === controller) {
        submitControllerRef.current = null;
        if (!controller.signal.aborted) {
          setIsSubmitting(false);
        }
      }
    }
  }

  const isRegistration = mode === "register";
  const errorDescriptionId = formError ? "auth-error" : undefined;
  const usernameDescriptionId = joinDescriptionIds(
    isRegistration ? "username-hint" : undefined,
    errorDescriptionId,
  );
  const passwordDescriptionId = joinDescriptionIds(
    isRegistration ? "password-hint" : undefined,
    errorDescriptionId,
  );
  const shouldShowSessionExpiredNotice = !isRegistration && showSessionExpiredNotice;
  const heading = isRegistration
    ? {
        eyebrow: messages.registerEyebrow,
        lead: messages.registerLead,
        title: messages.registerTitle,
      }
    : {
        eyebrow: messages.loginEyebrow,
        lead: messages.loginLead,
        title: messages.loginTitle,
      };
  const submitLabel = isRegistration
    ? isSubmitting
      ? messages.registerSubmitting
      : messages.registerSubmit
    : isSubmitting
      ? messages.loginSubmitting
      : messages.loginSubmit;

  return (
    <main className={styles.page}>
      <div aria-hidden="true" className={styles.ambient}>
        <span className={styles.ambientOrb} />
        <span className={styles.ambientLetter}>Aa</span>
        <span className={styles.ambientRule} />
      </div>

      <div className={styles.shell}>
        <section aria-hidden="true" className={styles.visual}>
          <p className={styles.brand}>Etch</p>
          <div className={styles.cardStack}>
            <span className={styles.wordCardBack} />
            <span className={styles.wordCardMiddle} />
            <span className={styles.wordCardFront}>
              <i>{messages.cardFront}</i>
              <b>{messages.cardBack}</b>
              <small>EN · RU</small>
            </span>
          </div>
          <div className={styles.visualCopy}>
            <span>{messages.visualLabel}</span>
            <strong>{messages.visualTitle}</strong>
          </div>
        </section>

        <div className={styles.login}>
          <div className={styles.headingGroup}>
            <span className={styles.eyebrow}>{heading.eyebrow}</span>
            <h1 className={styles.heading} id="auth-title">
              {heading.title}
            </h1>
            <p className={styles.lead}>{heading.lead}</p>
          </div>

          <section aria-labelledby="auth-title" className={styles.card}>
            <div aria-label={messages.modeLabel} className={styles.modeSwitch} role="group">
              <button
                aria-pressed={!isRegistration}
                className={styles.modeOption}
                disabled={isSubmitting}
                onClick={() => {
                  setMode("login");
                  setFormError(null);
                }}
                type="button"
              >
                {messages.loginMode}
              </button>
              <button
                aria-pressed={isRegistration}
                className={styles.modeOption}
                disabled={isSubmitting}
                onClick={() => {
                  setMode("register");
                  setFormError(null);
                }}
                type="button"
              >
                {messages.registerMode}
              </button>
            </div>

            {shouldShowSessionExpiredNotice ? (
              <p className={styles.notice} role="status">
                {messages.expired}
              </p>
            ) : null}
            <form
              aria-busy={isSubmitting}
              autoComplete="off"
              className={styles.form}
              onSubmit={handleSubmit}
              ref={formRef}
            >
              <div className={styles.field}>
                <label className={styles.label} htmlFor="username">
                  {messages.username} <span aria-hidden="true">*</span>
                </label>
                <input
                  aria-describedby={usernameDescriptionId}
                  aria-invalid={formError?.invalidFields ? true : undefined}
                  autoCapitalize="none"
                  autoComplete={isRegistration ? "username" : "off"}
                  autoCorrect="off"
                  className={styles.input}
                  disabled={isSubmitting}
                  id="username"
                  maxLength={USERNAME_MAX_LENGTH}
                  minLength={USERNAME_MIN_LENGTH}
                  name="username"
                  onAnimationStart={handleAutofillDetected}
                  onChange={(event) => setUsername(event.target.value)}
                  onFocus={enableFormInput}
                  onPointerDown={enableFormInput}
                  pattern="\S+"
                  readOnly={!isAcceptingInput && !isRegistration}
                  ref={usernameInputRef}
                  required
                  spellCheck={false}
                  type="text"
                  value={username}
                />
                {isRegistration ? (
                  <span className={styles.hint} id="username-hint">
                    {messages.usernameHint}
                  </span>
                ) : null}
              </div>

              {isRegistration ? (
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="email">
                    {messages.email} <span aria-hidden="true">*</span>
                  </label>
                  <input
                    aria-describedby={errorDescriptionId}
                    aria-invalid={formError?.invalidFields ? true : undefined}
                    autoCapitalize="none"
                    autoComplete="email"
                    autoCorrect="off"
                    className={styles.input}
                    disabled={isSubmitting}
                    id="email"
                    name="email"
                    onAnimationStart={handleAutofillDetected}
                    onChange={(event) => setEmail(event.target.value)}
                    onFocus={enableFormInput}
                    onPointerDown={enableFormInput}
                    readOnly={!isAcceptingInput && !isRegistration}
                    ref={emailInputRef}
                    required
                    spellCheck={false}
                    type="email"
                    value={email}
                  />
                </div>
              ) : null}

              <div className={styles.field}>
                <label className={styles.label} htmlFor="password">
                  {messages.password} <span aria-hidden="true">*</span>
                </label>
                <input
                  aria-describedby={passwordDescriptionId}
                  aria-invalid={formError?.invalidFields ? true : undefined}
                  autoComplete={isRegistration ? "new-password" : "off"}
                  className={styles.input}
                  disabled={isSubmitting}
                  id="password"
                  maxLength={PASSWORD_MAX_LENGTH}
                  minLength={PASSWORD_MIN_LENGTH}
                  name="password"
                  onAnimationStart={handleAutofillDetected}
                  onChange={(event) => setPassword(event.target.value)}
                  onFocus={enableFormInput}
                  onPointerDown={enableFormInput}
                  pattern="\S+"
                  readOnly={!isAcceptingInput && !isRegistration}
                  ref={passwordInputRef}
                  required
                  type="password"
                  value={password}
                />
                {isRegistration ? (
                  <span className={styles.hint} id="password-hint">
                    {messages.passwordHint}
                  </span>
                ) : null}
              </div>

              {formError ? (
                <p className={styles.error} id="auth-error" role="alert">
                  {formError.message}
                </p>
              ) : null}

              <button className={styles.submit} disabled={isSubmitting} type="submit">
                {submitLabel}
              </button>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}

export default LoginPage;
