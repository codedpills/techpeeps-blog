// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// Production origin. Set SITE_URL in your host (Cloudflare Pages → Settings →
// Environment variables) to your real domain so canonical URLs, Open Graph
// tags, the sitemap, and RSS resolve correctly. The fallback is only a
// placeholder for local builds.
const SITE_URL = process.env.SITE_URL || "https://techpeeps.example.com";

// https://astro.build/config
export default defineConfig({
  site: SITE_URL,
  output: "static",
  integrations: [sitemap()],
});
