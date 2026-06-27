# Tech Peeps Diaspora — Video-to-Blog Pipeline

A semi-automated pipeline that turns interview videos from the **Tech Peeps
Diaspora** YouTube channel into polished, feature-profile blog posts on a
self-hosted **Astro** static site, published through a **GitHub Pull Request
approval gate**. Every video is one host interviewing one guest (two speakers,
always). Nothing goes live without a human merge.

## How it works

```
yt-dlp playlist enumeration ─▶ state.json
        │
        ▼
yt-dlp audio ─▶ AssemblyAI (diarized, 2 speakers) ─▶ transcripts/<id>.json
        │
        ▼
Claude (feature-profile prompt) ─▶ draft .md on a branch
        │                         + hero clip (yt-dlp segment ─▶ ffmpeg silent MP4/WebM/poster)
        ▼
GitHub PR  ── human review ──▶ merge = publish ──▶ Astro build ──▶ deploy
```

## Repository layout

| Path | Purpose |
|---|---|
| `pipeline/` | Python pipeline (fetch, transcribe, clip, generate, style guide) |
| `pipeline/lib/` | shared helpers: `state`, `config`, `prompts`, `assemblyai`, `llm` |
| `transcripts/<id>.json` | committed diarized transcripts |
| `src/content/blog/` | **published posts only** (drafts live on branches) |
| `src/components/`, `src/layouts/`, `src/pages/` | Astro site |
| `public/clips/` | committed `<slug>.mp4` / `.webm` / `.jpg` |
| `state.json` | per-video status map |
| `style-guide.md` | one-time reusable host editorial voice |
| `work/` | gitignored scratch (downloads) |

## Setup

Prerequisites: **Python 3.10+**, **Node 18+**, **ffmpeg**, and the **GitHub CLI
(`gh`)** authenticated (`gh auth login`) or a `GITHUB_TOKEN`. On macOS install the
system tools with Homebrew: `brew install ffmpeg gh`. `yt-dlp` installs via pip
into the project virtualenv.

```bash
cp .env.example .env        # then fill in real values
make install                # creates .venv, installs Python deps there + npm
```

`make install` creates a project-local `.venv` and installs into it, so it works
on Homebrew Python (which blocks system-wide `pip install` via PEP 668). Every
`make` target runs Python through `.venv` automatically — you do **not** need to
activate it. If you run a script directly instead of via `make`, use the venv
interpreter: `.venv/bin/python pipeline/fetch_playlist.py`.

Required env vars (see `.env.example`): `ASSEMBLYAI_API_KEY`,
`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (defaults to `claude-sonnet-4-6`),
`GITHUB_TOKEN` (or rely on `gh` auth), `GITHUB_REPO`, `HOST_NAME`,
`YT_PLAYLIST_URL`. **Never commit `.env`.**

## One-time: build the host style guide

After transcribing 3–4 videos, capture the host's editorial voice once:

```bash
make transcribe ID=<id1>    # transcribe a few videos first
make transcribe ID=<id2>
make transcribe ID=<id3>
make style-guide            # -> style-guide.md (uses the longest 3-4)
```

Re-run only if the voice drifts.

## Per-video runbook

```bash
make fetch                 # refresh playlist into state.json
make next                  # transcribe + generate + open PR for the next video
# --- review the PR (see checklist below): confirm speakers, verify quotes,
#     set the hero clip, edit prose ---
# merge the PR             # = publish; site auto-deploys
make publish ID=<video_id> # mark state published (if not handled post-merge)
```

You can also run each step on a specific video:

```bash
make transcribe ID=<video_id>
make generate   ID=<video_id>
make clip ID=<video_id> START=01:23 END=01:28 SLUG=<slug>   # re-cut the hero clip
```

Status ladder: `pending → transcribed → drafted → published`. Each step is
idempotent; pass `--force` to a script to redo work.

If a transcript's HOST/GUEST labels look swapped (the heuristic handles
cold-open teaser clips and length-normalized question density, but isn't
infallible), re-run the mapping **without** re-transcribing — no API cost:

```bash
make remap                 # re-map every transcript in transcripts/
make remap ID=<video_id>   # re-map just one
```

Mappings flagged `confidence: low` are surfaced in the PR for you to confirm or
flip during review.

## The approval gate

Nothing publishes automatically — **the PR is the gate.** Each draft PR includes
this checklist:

- [ ] Speaker mapping correct (HOST vs GUEST not flipped) — *flagged if confidence low*
- [ ] Every quoted sentence is verbatim from the transcript
- [ ] No invented facts or quotes
- [ ] Hero clip is the right moment, silent, loops cleanly
- [ ] Title + description (≤155 chars) + 4–6 tags present
- [ ] Guest name/bio + video link correct

**Merging the PR = publishing. Reverting = unpublishing.** Full history is kept.
`generate.py` never writes to `main` and never marks a post `published`.

### Automated checks (the machine-verifiable half of the checklist)

`pipeline/verify_post.py` turns several checklist items into a hard gate:

- every multi-word quoted span must appear **verbatim** in the transcript
  (fails on a fabricated quote; warns if filler was removed inside quotes);
- frontmatter contract (title, description ≤155, 4–6 tags, heroClip, guest/bio);
- `videoUrl` matches `videoId` and contains no `PLACEHOLDER`;
- hero clip files exist, the MP4 is **silent** (checked with `ffprobe`) and small;
- `mapping_confidence: low` is surfaced as a warning.

It runs in three places: `make verify`, on every PR via CI, and inside
`generate.py` **before** a PR is opened (a hard failure commits the draft to the
branch for inspection but refuses to open the PR). Human-judgement items —
whether HOST/GUEST is truly correct, whether a paraphrase invents a *fact*,
whether the clip moment is right — remain manual.

## The site

Astro static site with a `blog` content collection validated by
`src/content/config.ts` (zod). A malformed draft **fails the build**. Hero clips
render as `<video autoplay loop muted playsinline>` with a poster fallback, so
they read like GIFs but stay small and sharp.

**Design:** a "paper screen" editorial look — a warm reading-paper light theme
and a dim warm dark theme. By default it follows the reader's system preference
(`prefers-color-scheme`); a floating toggle (top-right) lets them override and
the choice persists in `localStorage`. The toggle script is served from
`/public/scripts/theme.js` and loaded render-blocking so the saved theme applies
before first paint (no flash) — kept external to satisfy the strict CSP
(`script-src 'self'`, no inline scripts). Type is a book-serif stack (Iowan Old
Style / Palatino / Georgia) for reading with a system sans for small UI labels;
profile openings get a drop cap. All colors are CSS custom properties in
`public/styles/global.css`, so retheming is a one-file change.

```bash
make site-dev      # local dev server
make site-build    # production build (fails on invalid frontmatter)
```

### SEO & GEO

Built in and generated automatically at build time:

- **Sitemap** (`/sitemap-index.xml`) via `@astrojs/sitemap`, **RSS** (`/rss.xml`),
  and a dynamic **`/robots.txt`** that points at the sitemap.
- **Open Graph + Twitter** tags and a canonical URL on every page; the hero
  poster is the `og:image`.
- **JSON-LD structured data**: each profile emits `Article` + `Person` (the
  guest) + `VideoObject` (the source interview); the home page emits `Blog`.
  This is what drives Google rich results and lets AI/answer engines attribute
  and cite the content.
- **`/llms.txt`** — a curated, machine-readable index of published profiles for
  generative-search crawlers.
- Custom `404`, favicon, and `theme-color`.

## Deploying (Cloudflare Pages)

1. Push `main` to GitHub (already your remote).
2. In Cloudflare Pages, create a project from the repo with:
   - **Build command:** `npm run build`
   - **Output directory:** `dist`
3. **Set the `SITE_URL` environment variable** to your real domain (e.g.
   `https://techpeeps.dev`). Canonical URLs, OG tags, the sitemap, RSS, and
   `llms.txt` all derive from it — without it they fall back to a placeholder.
4. Security headers ship in `public/_headers` (CSP + HSTS + `X-Content-Type-Options`
   + `Referrer-Policy` + `Permissions-Policy`) and are applied by Cloudflare Pages
   automatically. If you later embed a YouTube `<iframe>`, widen the CSP `frame-src`
   as noted in that file.
5. Merging a post PR to `main` triggers an auto-deploy. Reverting unpublishes.

CI: `.github/workflows/ci.yml` runs `npm ci && npm run build` (plus a placeholder
guard) on every PR, so a malformed post can't merge.

### Previewing a draft on the PR (for the guest)

Each PR gets a Cloudflare Pages **preview deployment**. Production builds (the
`main` branch) never include drafts, but a **preview build renders the draft
post** so you can share it with the guest before publishing:

- Cloudflare sets `CF_PAGES_BRANCH` per build; `src/lib/site.ts` treats any
  non-production branch as a preview and includes `draft: true` posts only then.
- The draft renders with a "Draft preview" banner and `noindex`, and the whole
  preview deployment returns `robots.txt → Disallow: /`, so nothing leaks to
  search or to production.
- The guest visits `<preview-url>/blog/<slug>/`, reads it, and leaves edits on
  the PR. Merging to `main` publishes the real (banner-free, indexable) page.

Enable this in Cloudflare: Pages project → Settings → Builds & deployments →
ensure **preview deployments** are on (default) and the GitHub integration posts
the preview URL on each PR. If your production branch isn't `main`, set a
`PRODUCTION_BRANCH` environment variable to match.

> **Heads-up for the two PRs already open:** they were branched before this
> change, so their branches don't contain the preview logic yet. Merge the
> latest `main` into each branch (`git checkout <branch> && git merge main`) and
> push — the refreshed preview will then show the draft. Posts generated from now
> on branch off `main` and get it automatically.

## Notes

- All source footage is the channel owner's own content; clips and quotes link
  back to the source video.
- **Maintenance:** the site is pinned to Astro 4.x. `npm audit` reports advisories
  in Astro's SSR / dev-server / middleware code paths — this site uses none of
  them (it's fully static, no adapter/middleware), so production exposure is low,
  but plan a staged upgrade to the current Astro major when convenient.
