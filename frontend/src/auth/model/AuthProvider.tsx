import { useCallback, useEffect, useMemo, useReducer, useRef, type ReactNode } from "react";
import { apiClient } from "../../api";
import { getCurrentUser, loginRequest, logoutRequest } from "../api/auth-api";
import { AuthContext } from "./auth-context";
import { isAuthSessionRejected } from "./auth-errors";
import { authReducer, initialAuthState } from "./auth-reducer";
import { withAuthMutationLock } from "./auth-mutation-lock";
import { clearSessionCache, ensureSessionCache, startSessionCache } from "./session-cache";
import { setUnauthorizedListener } from "./auth-session";
import {
  getCurrentAuthSessionSequence,
  publishAuthSessionEvent,
  subscribeToAuthSessionEvents,
  type AuthSessionEventInput,
} from "./auth-session-events";
import type { AuthContextValue, LoginCredentials } from "./auth-types";
import type { UserSettings } from "../../features/settings/model/settings-types";

interface AuthProviderProps {
  children: ReactNode;
}

interface AuthOperation {
  controller: AbortController;
  operation: number;
  signal: AbortSignal;
}

const SUPERSEDED_REASON = "auth-operation-superseded";
const LOGOUT_REASON = "auth-logout";
const SESSION_SYNC_REASON = "auth-session-sync";
const SESSION_INVALIDATED_REASON = "auth-session-invalidated";

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error("An unknown authentication error occurred.");
}

function shouldDeferCookieCleanup(signal: AbortSignal): boolean {
  return (
    signal.reason === LOGOUT_REASON ||
    signal.reason === SESSION_SYNC_REASON ||
    signal.reason === SUPERSEDED_REASON
  );
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, dispatch] = useReducer(authReducer, initialAuthState);
  const mountedRef = useRef(true);
  const operationRef = useRef(0);
  const activeOperationRef = useRef<AbortController | null>(null);
  const initializationRef = useRef<Promise<void> | null>(null);
  const loginMutationRef = useRef<Promise<void> | null>(null);
  const logoutPendingRef = useRef(false);
  const latestSessionEventRef = useRef(getCurrentAuthSessionSequence());

  const isCurrentOperation = useCallback(
    (operation: number) => mountedRef.current && operation === operationRef.current,
    [],
  );

  const beginOperation = useCallback(
    (externalSignal?: AbortSignal, replacementReason = SUPERSEDED_REASON): AuthOperation => {
      activeOperationRef.current?.abort(replacementReason);

      const controller = new AbortController();
      activeOperationRef.current = controller;
      const signal = externalSignal
        ? AbortSignal.any([controller.signal, externalSignal])
        : controller.signal;

      return {
        controller,
        operation: ++operationRef.current,
        signal,
      };
    },
    [],
  );

  const finishOperation = useCallback((controller: AbortController): void => {
    if (activeOperationRef.current === controller) {
      activeOperationRef.current = null;
    }
  }, []);

  const publishSessionEvent = useCallback((event: AuthSessionEventInput): void => {
    latestSessionEventRef.current = publishAuthSessionEvent(event);
  }, []);

  const initialize = useCallback((): Promise<void> => {
    if (initializationRef.current) {
      return initializationRef.current;
    }

    const { controller, operation, signal } = beginOperation();
    dispatch({ type: "loading" });

    const initialization = (async () => {
      try {
        const user = await getCurrentUser(signal);
        if (isCurrentOperation(operation) && !signal.aborted) {
          startSessionCache(user.uuid);
          dispatch({ type: "authorized", user });
        }
      } catch (error) {
        if (!isCurrentOperation(operation) || signal.aborted) {
          return;
        }

        if (isAuthSessionRejected(error)) {
          apiClient.invalidateSession();
          clearSessionCache();
          dispatch({ type: "unauthorized" });
        } else {
          dispatch({ type: "error", error: toError(error) });
        }
      } finally {
        finishOperation(controller);
      }
    })();
    initializationRef.current = initialization;
    void initialization.finally(() => {
      if (initializationRef.current === initialization) {
        initializationRef.current = null;
      }
    });

    return initialization;
  }, [beginOperation, finishOperation, isCurrentOperation]);

  const login = useCallback(
    (credentials: LoginCredentials, externalSignal?: AbortSignal): Promise<void> => {
      latestSessionEventRef.current = Math.max(
        latestSessionEventRef.current,
        getCurrentAuthSessionSequence(),
      );
      const { controller, operation, signal } = beginOperation(externalSignal);
      let sessionStarted = false;

      const loginMutation = withAuthMutationLock(async () => {
        try {
          await loginRequest(credentials, signal);
          if (signal.aborted) {
            if (!shouldDeferCookieCleanup(signal)) {
              try {
                await logoutRequest();
              } catch {
                // An aborted component still leaves the UI signed out if cleanup is unavailable.
              }
              clearSessionCache();
              publishSessionEvent({ type: "signed-out" });
            }
            return;
          }

          if (!isCurrentOperation(operation)) {
            return;
          }

          apiClient.startSession();
          sessionStarted = true;

          const user = await getCurrentUser(signal, false);
          if (isCurrentOperation(operation) && !signal.aborted) {
            startSessionCache(user.uuid);
            dispatch({ type: "authorized", user });
            publishSessionEvent({ type: "signed-in" });
          }
        } catch (error) {
          const needsOwnCookieCleanup =
            (sessionStarted && !signal.aborted) ||
            (signal.aborted && !shouldDeferCookieCleanup(signal));

          if (needsOwnCookieCleanup) {
            apiClient.invalidateSession();
            clearSessionCache();
            try {
              await logoutRequest();
            } catch {
              // The UI still fails closed when post-login identity loading fails.
            }
            publishSessionEvent({ type: "signed-out" });
          }

          if (isCurrentOperation(operation) && !signal.aborted) {
            clearSessionCache();
            dispatch({ type: "unauthorized" });
          }

          if (!signal.aborted) {
            throw error;
          }
        } finally {
          finishOperation(controller);
        }
      }, signal);

      loginMutationRef.current = loginMutation;
      void loginMutation.then(
        () => {
          if (loginMutationRef.current === loginMutation) {
            loginMutationRef.current = null;
          }
        },
        () => {
          if (loginMutationRef.current === loginMutation) {
            loginMutationRef.current = null;
          }
        },
      );

      return loginMutation;
    },
    [beginOperation, finishOperation, isCurrentOperation, publishSessionEvent],
  );

  const refresh = useCallback(
    async (externalSignal?: AbortSignal): Promise<void> => {
      const { controller, operation, signal } = beginOperation(externalSignal);

      try {
        await apiClient.refreshSession(signal);
        if (signal.aborted) {
          return;
        }

        const user = await getCurrentUser(signal);
        if (isCurrentOperation(operation) && !signal.aborted) {
          ensureSessionCache(user.uuid);
          dispatch({ type: "authorized", user });
        }
      } catch (error) {
        if (!isCurrentOperation(operation) || signal.aborted) {
          return;
        }

        if (isAuthSessionRejected(error)) {
          apiClient.invalidateSession();
          clearSessionCache();
          dispatch({ type: "unauthorized" });
        } else {
          dispatch({ type: "error", error: toError(error) });
        }
        throw error;
      } finally {
        finishOperation(controller);
      }
    },
    [beginOperation, finishOperation, isCurrentOperation],
  );

  const logout = useCallback(
    async (signal?: AbortSignal): Promise<void> => {
      latestSessionEventRef.current = Math.max(
        latestSessionEventRef.current,
        getCurrentAuthSessionSequence(),
      );
      const pendingLogin = loginMutationRef.current;
      logoutPendingRef.current = true;
      activeOperationRef.current?.abort(LOGOUT_REASON);
      activeOperationRef.current = null;
      operationRef.current += 1;
      apiClient.invalidateSession();
      clearSessionCache();
      dispatch({ type: "unauthorized" });

      if (pendingLogin) {
        try {
          await pendingLogin;
        } catch {
          // Logout is sent after the login transport settles, regardless of its result.
        }
      }

      try {
        await withAuthMutationLock(async () => {
          try {
            await logoutRequest(signal);
          } catch {
            if (signal?.aborted) {
              try {
                await logoutRequest();
              } catch {
                // Local logout is authoritative even when server cleanup is unavailable.
              }
            }
          } finally {
            publishSessionEvent({ type: "signed-out" });
          }
        });
      } finally {
        logoutPendingRef.current = false;
      }
    },
    [publishSessionEvent],
  );

  const applyUserSettings = useCallback((settings: UserSettings): void => {
    dispatch({ type: "settings-updated", settings });
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    setUnauthorizedListener((error) => {
      activeOperationRef.current?.abort(SESSION_INVALIDATED_REASON);
      activeOperationRef.current = null;
      operationRef.current += 1;
      if (mountedRef.current) {
        dispatch(
          isAuthSessionRejected(error)
            ? { type: "unauthorized" }
            : { type: "error", error: toError(error) },
        );
      }
    });

    const unsubscribe = subscribeToAuthSessionEvents((event) => {
      if (event.sequence <= latestSessionEventRef.current) {
        return;
      }
      latestSessionEventRef.current = event.sequence;

      if (logoutPendingRef.current || loginMutationRef.current) {
        return;
      }

      if (event.type === "signed-out") {
        activeOperationRef.current?.abort(SESSION_SYNC_REASON);
        activeOperationRef.current = null;
        operationRef.current += 1;
        apiClient.invalidateSession();
        clearSessionCache();
        if (mountedRef.current) {
          dispatch({ type: "unauthorized" });
        }
        return;
      }

      clearSessionCache();
      const { controller, operation, signal } = beginOperation(undefined, SESSION_SYNC_REASON);
      apiClient.startSession();
      dispatch({ type: "loading" });

      void (async () => {
        try {
          const user = await getCurrentUser(signal);
          if (isCurrentOperation(operation) && !signal.aborted) {
            startSessionCache(user.uuid);
            dispatch({ type: "authorized", user });
          }
        } catch (error) {
          if (isCurrentOperation(operation) && !signal.aborted) {
            apiClient.invalidateSession();
            dispatch(
              isAuthSessionRejected(error)
                ? { type: "unauthorized" }
                : { type: "error", error: toError(error) },
            );
          }
        } finally {
          finishOperation(controller);
        }
      })();
    });

    void initialize();

    return () => {
      mountedRef.current = false;
      setUnauthorizedListener(null);
      unsubscribe();
    };
  }, [beginOperation, finishOperation, initialize, isCurrentOperation]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      isAuthenticated: state.status === "authorized",
      initialize,
      login,
      logout,
      refresh,
      applyUserSettings,
    }),
    [applyUserSettings, initialize, login, logout, refresh, state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
