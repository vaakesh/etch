import type { PracticeHistoryFilter } from "./practice-types";

type PracticeHistoryCacheListener = () => void;

const invalidationVersions = new Map<PracticeHistoryFilter, number>();
const invalidationListeners = new Map<PracticeHistoryFilter, Set<PracticeHistoryCacheListener>>();

export function getPracticeHistoryInvalidationVersion(filter: PracticeHistoryFilter): number {
  return invalidationVersions.get(filter) ?? 0;
}

export function invalidatePracticeHistory(filters: readonly PracticeHistoryFilter[]): void {
  filters.forEach((filter) => {
    invalidationVersions.set(filter, getPracticeHistoryInvalidationVersion(filter) + 1);
    invalidationListeners.get(filter)?.forEach((listener) => listener());
  });
}

export function subscribeToPracticeHistoryInvalidation(
  filter: PracticeHistoryFilter,
  listener: PracticeHistoryCacheListener,
): () => void {
  const listeners = invalidationListeners.get(filter) ?? new Set<PracticeHistoryCacheListener>();
  listeners.add(listener);
  invalidationListeners.set(filter, listeners);

  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      invalidationListeners.delete(filter);
    }
  };
}
