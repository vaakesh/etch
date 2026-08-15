import { useAuth } from "../../../auth/hooks/useAuth";

export function useLongTextPreviewsEnabled(): boolean {
  const { user } = useAuth();

  return user?.settings.showPreviewsForLong ?? true;
}
