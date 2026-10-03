export interface SessionCacheScope {
  readonly userUuid: string;
  readonly sessionRevision: number;
  readonly key: string;
}

export interface SessionCacheKey<TValue> {
  readonly id: symbol;
  readonly label: string;
  readonly valueType?: (value: TValue) => TValue;
}

interface SessionCacheStore {
  readonly scope: SessionCacheScope;
  readonly entries: Map<symbol, unknown>;
}

type SessionCacheListener = () => void;

let sessionRevision = 0;
let currentStore: SessionCacheStore | null = null;
const listeners = new Set<SessionCacheListener>();

function notifyScopeChange(): void {
  listeners.forEach((listener) => listener());
}

export function createSessionCacheKey<TValue>(label: string): SessionCacheKey<TValue> {
  return { id: Symbol(label), label };
}

export function startSessionCache(userUuid: string): SessionCacheScope {
  sessionRevision += 1;
  const scope: SessionCacheScope = {
    userUuid,
    sessionRevision,
    key: `${userUuid}:${sessionRevision}`,
  };
  currentStore = { scope, entries: new Map() };
  notifyScopeChange();
  return scope;
}

export function ensureSessionCache(userUuid: string): SessionCacheScope {
  if (currentStore?.scope.userUuid === userUuid) {
    return currentStore.scope;
  }

  return startSessionCache(userUuid);
}

export function clearSessionCache(): void {
  sessionRevision += 1;
  const hadActiveSession = currentStore !== null;
  currentStore = null;
  if (hadActiveSession) {
    notifyScopeChange();
  }
}

export function getCurrentSessionCacheScope(): SessionCacheScope | null {
  return currentStore?.scope ?? null;
}

export function isSessionCacheScopeActive(
  scope: SessionCacheScope | null,
): scope is SessionCacheScope {
  return scope !== null && currentStore?.scope.key === scope.key;
}

export function getSessionCacheEntry<TValue>(
  scope: SessionCacheScope | null,
  cacheKey: SessionCacheKey<TValue>,
): TValue | undefined {
  if (!isSessionCacheScopeActive(scope)) {
    return undefined;
  }

  return currentStore?.entries.get(cacheKey.id) as TValue | undefined;
}

export function setSessionCacheEntry<TValue>(
  scope: SessionCacheScope | null,
  cacheKey: SessionCacheKey<TValue>,
  value: TValue,
): boolean {
  if (!isSessionCacheScopeActive(scope) || currentStore === null) {
    return false;
  }

  currentStore.entries.set(cacheKey.id, value);
  return true;
}

export function deleteSessionCacheEntry<TValue>(
  scope: SessionCacheScope | null,
  cacheKey: SessionCacheKey<TValue>,
): boolean {
  if (!isSessionCacheScopeActive(scope) || currentStore === null) {
    return false;
  }

  return currentStore.entries.delete(cacheKey.id);
}

export function subscribeToSessionCacheScope(listener: SessionCacheListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
