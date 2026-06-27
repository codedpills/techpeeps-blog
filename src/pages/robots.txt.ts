import type { APIRoute } from "astro";
import { isPreviewBuild } from "../lib/site";

// Dynamic robots.txt. On Cloudflare preview deployments we disallow everything
// so draft preview URLs never get indexed. On production we allow crawling and
// point at the sitemap (URL always matches the configured SITE_URL origin).
export const GET: APIRoute = ({ site }) => {
  if (isPreviewBuild()) {
    return new Response("User-agent: *\nDisallow: /\n", {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
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
