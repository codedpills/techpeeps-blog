import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

// llms.txt — an emerging convention that gives AI / answer engines a concise,
// curated map of the site's canonical content. Generated dynamically so it
// always reflects the published posts.
export const GET: APIRoute = async ({ site }) => {
  const posts = (await getCollection("blog")).sort(
    (a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf(),
  );
  const origin = site?.toString().replace(/\/$/, "") ?? "";

  const lines = [
    "# Tech Peeps Diaspora",
    "",
    "> Feature profiles of tech professionals across the diaspora, drawn from",
    "> the Tech Peeps Diaspora interview series. Each profile is written from a",
    "> diarized interview transcript; all direct quotes are verbatim.",
    "",
    "## Profiles",
    "",
    ...posts.map(
      (p) =>
        `- [${p.data.title}](${origin}/blog/${p.slug}/): ${p.data.guest} — ${p.data.description}`,
    ),
    "",
    "## Source",
    "",
    "- [Tech Peeps Diaspora on YouTube](https://www.youtube.com/@techpeepsdiaspora)",
    "",
  ];

  return new Response(lines.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
