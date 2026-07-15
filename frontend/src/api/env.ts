function normalizeApiBaseUrl(value: string | undefined): string {
  const baseUrl = value?.trim() || "/api";
  const isAbsoluteHttpUrl = /^https?:\/\//u.test(baseUrl);
  const isRootRelativeUrl = baseUrl.startsWith("/");

  if (!isAbsoluteHttpUrl && !isRootRelativeUrl) {
    throw new Error("VITE_API_URL must be an absolute HTTP(S) URL or a root-relative path.");
  }

  return baseUrl === "/" ? "" : baseUrl.replace(/\/$/u, "");
}

export const env = Object.freeze({
  apiBaseUrl: normalizeApiBaseUrl(import.meta.env.VITE_API_URL),
});
