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

// Content-collection filter. Visibility is decided by WHICH branch is building,
// not by the `draft` frontmatter flag: a post lives under src/content/blog only
// on its PR branch (preview) or on main (published), so every committed post
// should render. Merge to main = published. The preview-vs-production split only
// drives noindex + the preview banner (see isPreviewBuild). The `draft` flag is
// retained in the schema for compatibility but no longer gates visibility.
export function postFilter(_entry: { data: { draft?: boolean } }): boolean {
  return true;
}
