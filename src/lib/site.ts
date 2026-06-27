// Build-environment helpers.
//
// A Cloudflare Pages *preview* deployment builds a non-production branch (i.e.
// the PR branch). We render draft posts ONLY on previews so a guest can review
// their profile via the PR's preview URL before it's merged/published.
// Production (the main branch) never includes drafts.

const PRODUCTION_BRANCH = process.env.PRODUCTION_BRANCH || "main";

export function isPreviewBuild(): boolean {
  // Explicit override (handy for `PREVIEW_DRAFTS=true npm run build` locally).
  if (process.env.PREVIEW_DRAFTS === "true") return true;
  if (process.env.PREVIEW_DRAFTS === "false") return false;

  // Cloudflare Pages sets CF_PAGES=1 and CF_PAGES_BRANCH on every build.
  if (process.env.CF_PAGES === "1") {
    return (process.env.CF_PAGES_BRANCH || "") !== PRODUCTION_BRANCH;
  }
  return false;
}

// On preview we surface drafts; everywhere else only published posts.
export function includeDrafts(): boolean {
  return isPreviewBuild();
}

// Content-collection filter: keep published posts always, drafts only on preview.
export function postFilter({ data }: { data: { draft?: boolean } }): boolean {
  return includeDrafts() || !data.draft;
}
