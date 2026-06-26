import type { APIRoute } from "astro";

// Dynamic robots.txt so the Sitemap URL always matches the configured site
// origin (SITE_URL) instead of a hardcoded placeholder.
export const GET: APIRoute = ({ site }) => {
  const sitemap = new URL("sitemap-index.xml", site).href;
  const body = `User-agent: *
Allow: /

# AI / generative-search crawlers are welcome to read and cite this content.

Sitemap: ${sitemap}
`;
  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
