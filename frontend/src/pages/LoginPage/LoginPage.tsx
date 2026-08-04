import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type AnimationEvent as ReactAnimationEvent,
  type FormEvent,
} from "react";
import { useLocation } from "react-router-dom";
import { isApiError } from "../../api";
import { hasSessionExpiredNotice } from "../../app/router/navigation-state";
import { useAuth } from "../../auth/hooks/useAuth";
import styles from "./LoginPage.module.css";

const INVALID_CREDENTIALS_STATUSES = new Set([401, 403, 404]);
const USERNAME_MIN_LENGTH = 3;
const USERNAME_MAX_LENGTH = 18;
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_LENGTH = 128;

function getLoginErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (INVALID_CREDENTIALS_STATUSES.has(error.status)) {
      return "Неверное имя пользователя или пароль.";
    }

    if (error.status === 422) {
      return "Имя пользователя — 3–18 символов без пробелов, пароль — 8–128 символов без пробелов.";
    }

    if (error.status === 0) {
      return "Не удалось связаться с сервером. Попробуйте ещё раз.";
    }
  }

  return "Не удалось войти. Попробуйте ещё раз.";
}

export function LoginPage() {
  const { login } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAcceptingInput, setIsAcceptingInput] = useState(false);
  const formRef = useRef<HTMLFormElement | null>(null);
  const usernameInputRef = useRef<HTMLInputElement | null>(null);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const submitControllerRef = useRef<AbortController | null>(null);

  const clearRenderedFields = useCallback((): void => {
    formRef.current?.reset();

    if (usernameInputRef.current) {
      usernameInputRef.current.value = "";
    }
    if (passwordInputRef.current) {
      passwordInputRef.current.value = "";
    }
  }, []);

  const clearForm = useCallback((): void => {
    setUsername("");
    setPassword("");
    setErrorMessage(null);
    setIsSubmitting(false);
    setIsAcceptingInput(false);
    clearRenderedFields();
  }, [clearRenderedFields]);

  const enableFormInput = useCallback((): void => {
    if (isAcceptingInput) {
      return;
    }

    clearForm();
    setIsAcceptingInput(true);
  }, [clearForm, isAcceptingInput]);

  const handleAutofillDetected = useCallback(
    (event: ReactAnimationEvent<HTMLInputElement>): void => {
      if (isAcceptingInput) {
        return;
      }

      event.currentTarget.value = "";
      if (event.currentTarget === usernameInputRef.current) {
        setUsername("");
      }
      if (event.currentTarget === passwordInputRef.current) {
        setPassword("");
      }
    },
    [isAcceptingInput],
  );

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
      setErrorMessage("Введите имя пользователя.");
      return;
    }

    const controller = new AbortController();
    submitControllerRef.current?.abort();
    submitControllerRef.current = controller;
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await login({ username: normalizedUsername, password }, controller.signal);
      if (!controller.signal.aborted) {
        setUsername("");
        setPassword("");
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setErrorMessage(getLoginErrorMessage(error));
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

  const errorDescriptionId = errorMessage ? "login-error" : undefined;
  const showSessionExpiredNotice = hasSessionExpiredNotice(location.state);

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
              <i>hello</i>
              <b>привет</b>
              <small>EN · RU</small>
            </span>
          </div>
          <div className={styles.visualCopy}>
            <span>Ваш словарь</span>
            <strong>Слова, которые остаются с вами.</strong>
          </div>
        </section>

        <div className={styles.login}>
          <div className={styles.headingGroup}>
            <span className={styles.eyebrow}>Личный кабинет</span>
            <h1 className={styles.heading} id="login-title">
              С возвращением
            </h1>
            <p className={styles.lead}>Продолжите учиться с того места, где остановились.</p>
          </div>

          <section aria-labelledby="login-title" className={styles.card}>
            {showSessionExpiredNotice ? (
              <p className={styles.notice} role="status">
                Сессия истекла. Войдите снова.
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
                  Имя пользователя <span aria-hidden="true">*</span>
                </label>
                <input
                  aria-describedby={errorDescriptionId}
                  aria-invalid={errorMessage ? true : undefined}
                  autoCapitalize="none"
                  autoComplete="off"
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
                  readOnly={!isAcceptingInput}
                  ref={usernameInputRef}
                  required
                  spellCheck={false}
                  type="text"
                  value={username}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="password">
                  Пароль <span aria-hidden="true">*</span>
                </label>
                <input
                  aria-describedby={errorDescriptionId}
                  aria-invalid={errorMessage ? true : undefined}
                  autoComplete="off"
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
                  readOnly={!isAcceptingInput}
                  ref={passwordInputRef}
                  required
                  type="password"
                  value={password}
                />
              </div>

              {errorMessage ? (
                <p className={styles.error} id="login-error" role="alert">
                  {errorMessage}
                </p>
              ) : null}

              <button className={styles.submit} disabled={isSubmitting} type="submit">
                {isSubmitting ? "Входим…" : "Войти"}
              </button>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}

export default LoginPage;
