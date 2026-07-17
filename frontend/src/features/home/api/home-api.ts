import { apiFetch } from "../../../api";
import { parseHomeDashboard } from "../model/home-contract";
import type { HomeDashboard } from "../model/home-types";

const HOME_DASHBOARD_PATH = "/bff/home";

export async function getHomeDashboard(signal?: AbortSignal): Promise<HomeDashboard> {
  const payload = await apiFetch<unknown>(HOME_DASHBOARD_PATH, { signal });
  return parseHomeDashboard(payload);
}
