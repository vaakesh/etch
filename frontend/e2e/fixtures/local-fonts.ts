import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import type { BrowserContext } from "@playwright/test";

const require = createRequire(import.meta.url);
const packages = [
  { name: "inter", family: "Inter" },
  { name: "playfair-display", family: "Playfair Display" },
];

// Only font resources are substituted, including in integration; API is untouched.
export async function installLocalFonts(context: BrowserContext, baseURL: string): Promise<void> {
  const assets = new Map<string, string>();
  const styles: string[] = [];
  const origin = new URL(baseURL).origin;
  for (const font of packages) {
    const cssPath = require.resolve(`@fontsource-variable/${font.name}/index.css`);
    const source = await readFile(cssPath, "utf8");
    styles.push(
      source
        .replaceAll(`${font.family} Variable`, font.family)
        .replace(/url\(\.\/files\/([^ )]+)\)/g, (_match: string, file: string) => {
          const pathname = `/__e2e_fonts/${font.name}/${file}`;
          assets.set(pathname, join(dirname(cssPath), "files", file));
          return `url(${origin}${pathname})`;
        }),
    );
  }
  await context.route(
    (url) => url.hostname === "fonts.googleapis.com" && url.pathname === "/css2",
    async (route) => {
      await route.fulfill({ contentType: "text/css", body: styles.join("\n") });
    },
  );
  await context.route(
    (url) => url.origin === origin && url.pathname.startsWith("/__e2e_fonts/"),
    async (route) => {
      const file = assets.get(new URL(route.request().url()).pathname);
      if (!file) throw new Error("Unknown local font asset");
      await route.fulfill({ contentType: "font/woff2", path: file });
    },
  );
}
