import { useSyncExternalStore } from "react";
import {
  getCurrentSessionCacheScope,
  subscribeToSessionCacheScope,
  type SessionCacheScope,
} from "../model/session-cache";

export function useSessionCacheScope(): SessionCacheScope | null {
  return useSyncExternalStore(
    subscribeToSessionCacheScope,
    getCurrentSessionCacheScope,
    getCurrentSessionCacheScope,
  );
}
