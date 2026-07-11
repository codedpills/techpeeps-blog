// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// Production origin. Set SITE_URL in your host (Cloudflare Pages → Settings →
// Environment variables) to your real domain so canonical URLs, Open Graph
// tags, the sitemap, and RSS resolve correctly. The fallback is only a
// placeholder for local builds.
const FALLBACK_SITE = "https://techpeeps.example.com";

// Be forgiving about how SITE_URL is entered in the host's env: accept a value
// without a scheme (e.g. "blog.techpeepsdiaspora.com"), strip trailing slashes,
// and fall back if it still isn't a valid URL — so a mis-typed env var can never
// fail the production build with "site: Invalid url".
function normalizeSite(raw) {
  let s = (raw || "").trim();
  if (!s) return FALLBACK_SITE;
  if (!/^https?:\/\//i.test(s)) s = "https://" + s;
  s = s.replace(/\/+$/, "");
  try {
    new URL(s);
  } catch {
    return FALLBACK_SITE;
  }
  return s;
}

const SITE_URL = normalizeSite(process.env.SITE_URL);

// https://astro.build/config
export default defineConfig({
  site: SITE_URL,
  output: "static",
  integrations: [sitemap()],
});
