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
| `pipeline/` | Python pipeline: `fetch_playlist`, `transcribe`, `clip`, `generate`, `make_style_guide`, `verify_post`, `compare_models`, `mark_published` |
| `pipeline/lib/` | shared helpers: `state`, `config`, `prompts`, `assemblyai`, `llm` |
| `transcripts/<id>.json` | committed diarized transcripts |
| `src/content/blog/` | **published posts only** (drafts live on branches) |
| `src/components/`, `src/layouts/`, `src/pages/` | Astro site (incl. `ThemeToggle`) |
| `src/lib/site.ts` | build-env helpers (preview-vs-production, draft inclusion) |
| `public/clips/` | committed `<slug>.mp4` / `.webm` / `.jpg` |
| `public/styles/`, `public/scripts/` | global CSS + the theme-toggle script |
| `public/_headers` | Cloudflare security headers (CSP, HSTS, …) |
| `.github/workflows/ci.yml` | build + content-check, sticky PR comment |
| `state.json` | per-video status map |
| `style-guide.md` | one-time reusable host editorial voice |
| `work/` | gitignored scratch (downloads, `compare/` outputs) |

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
make fetch                              # refresh ALL registered playlists
make fetch PLAYLIST=<youtube-url>       # register a new playlist, then refresh all
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

### Multiple playlists

`state.json` tracks a **list** of playlists (`playlists: [...]`) and tags each
video with the playlist it came from (`videos.<id>.playlist`). Add one with
`make fetch PLAYLIST=<url>`; a bare `make fetch` re-enumerates every registered
playlist. Video IDs are globally unique, so playlists never collide, and the rest
of the pipeline (transcribe → generate → publish) is unchanged regardless of
which playlist a video belongs to. The legacy single `playlist_url` field is
auto-migrated into the list on first load. (The per-video `playlist` tag also
sets you up to group posts by series on the site later, if you want.)

Status ladder: `pending → transcribed → drafted → published`. Each step is
idempotent. To redo work, pass flags as **make variables** (not as `--flags`,
which `make` would try to parse itself):

```bash
make transcribe ID=<id> FORCE=1     # re-transcribe
make generate   ID=<id> FORCE=1     # regenerate the draft
make generate   ID=<id> NOPR=1      # local branch only, no PR
```

### Multi-part interviews (one story split across videos)

When a single conversation was uploaded as two (or more) YouTube videos — e.g.
"… (Part 1)" and "… (Part 2)" — combine them into **one** profile instead of
letting each part become its own post. Transcribe every part first, then pass the
ids as a comma-separated list, primary (the one you want to link back to) first:

```bash
make transcribe ID=<part1_id>
make transcribe ID=<part2_id>
make generate   ID="<part1_id>,<part2_id>"
```

`generate` merges the transcripts into one prompt (the model is told to treat
them as a single continuous conversation), cuts the hero clip from the primary
video, and writes the primary id to `videoId` plus **all** part ids to a
`sources:` frontmatter list. Quote verification then checks quotes against the
**union** of every part's transcript, and each part is marked `drafted` against
the one slug/PR so a part can't be re-drafted into a duplicate post later.

### A/B comparing models

To choose between models for the writing, run both on the same transcript without
touching git or opening a PR:

```bash
make compare ID=<id>                                   # defaults: opus vs sonnet
make compare ID=<id> MODELS=claude-opus-4-8,claude-sonnet-4-6
```

It writes one article per model to `work/compare/` (gitignored) to read side by
side. Once you've decided, set `ANTHROPIC_MODEL` in `.env` and run a normal
`make generate ID=<id> FORCE=1`.

### Dates: published vs. interview

Each post shows two dates in its sub-header — **when the article was published**
on the site (`pubDate`, set to generation day) and **when the interview aired on
YouTube** (`interviewDate`). The latter is captured automatically at transcribe
time (yt-dlp `upload_date`, stored as `video_published_at` in the transcript) and
injected into the frontmatter by `generate.py`; it also drives the JSON-LD
`VideoObject.uploadDate`. New drafts get it for free.

To backfill posts that were drafted before this existed:

```bash
make refresh-meta          # fetch publish dates into all transcripts + state
make patch-dates           # inject interviewDate onto each open drafted PR branch
# then push the patched branches to update their PRs
```

`refresh-meta`/`patch-dates` accept `ID=<video_id>` to target one. A missing
`interviewDate` is a **warning** (not a blocker) in the verifier.

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

`pipeline/verify_post.py` checks several checklist items automatically:

- every multi-word quoted span must appear **verbatim** in the transcript
  (**error** on a fabricated quote; **warning** if filler was removed inside quotes);
- frontmatter contract (title, description ≤155, 4–6 tags, heroClip, guest/bio);
- `videoUrl` matches `videoId` and contains no `PLACEHOLDER`;
- hero clip files exist, the MP4 is **silent** (checked with `ffprobe`) and small;
- `mapping_confidence: low` is surfaced as a warning.

**These checks never block PR creation or the preview** — the philosophy is to
surface issues for review, not hide the draft. Specifically:

- `generate.py` always opens the PR and **embeds the findings (with suggested
  fixes) in the PR description**.
- CI (`.github/workflows/ci.yml`) re-runs the verifier on every push and posts a
  single **sticky PR comment** with the issues + fixes, updated each time.
- The CI check goes **red only on hard errors** (fabricated quote, invalid
  frontmatter, leftover placeholder, clip-with-audio); warnings never fail it.
  A red check still leaves the PR and its Cloudflare preview fully usable — it
  only blocks *merge* if you enable branch protection requiring the `build`
  check. `make verify` runs the same checks locally; `--no-fail` makes it
  advisory.

Human-judgement items — whether HOST/GUEST is truly correct, whether a paraphrase
invents a *fact*, whether the clip moment is right — remain manual.

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

CI: `.github/workflows/ci.yml` runs the content verifier and `npm run build` on
every PR and push, and posts the verifier's findings as a sticky PR comment (see
[Automated checks](#automated-checks-the-machine-verifiable-half-of-the-checklist)).
The job is named **`build`** — require it via branch protection (below) to
actually block merges on hard errors.

## Branch protection (enforce the gate)

The CI check is advisory until you require it. To make `main` un-mergeable while
the `build` check is red:

1. Push `main` and open a PR once so the `build` check has run and is selectable.
2. GitHub → repo **Settings → Branches → Add branch protection rule** (or
   **Settings → Rules → Rulesets**), pattern `main`.
3. Enable **Require a pull request before merging** (blocks direct pushes;
   approvals can be `0` if you're the sole reviewer).
4. Enable **Require status checks to pass before merging** and select **`build`**.
   Optionally **Require branches to be up to date**.
5. Save. A PR with a red `build` check now can't be merged, while its Cloudflare
   preview stays usable for guest review.

Scripted equivalent (run locally; needs repo admin):

```bash
gh api --method PUT repos/$GITHUB_REPO/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["build"] },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "restrictions": null
}
JSON
```

Because the content verifier and the Astro build are the **same** `build` job,
requiring it gates on both fabricated-quote errors and frontmatter errors.
Warnings never fail the job, so they never block merge.

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

> **Note:** a PR branch only has the site/pipeline behavior that existed on
> `main` when it was cut. If you change `main` (theme, preview logic, CI) while a
> PR is open, merge `main` into that branch to refresh its preview:
> `git checkout <branch> && git merge main && git push`. Newly generated posts
> branch off the current `main`, so they pick everything up automatically.

## Newsletter (MailerLite)

Readers subscribe from the home page. The signup form posts to a same-origin
**Cloudflare Pages Function** (`functions/api/subscribe.js`), which forwards the
email to MailerLite's API server-side — so the browser never calls MailerLite and
the CSP needs no changes. Behavior lives in `public/scripts/subscribe.js`
(progressive enhancement: the form still works without JS). A honeypot field
filters bots; MailerLite handles double opt-in, unsubscribe, and compliance.

Set these as **Cloudflare Pages environment variables** (Settings → Environment
variables, marked as secrets — never commit them):

- `MAILERLITE_API_KEY` — token from MailerLite → Integrations → API
- `MAILERLITE_GROUP_ID` — the "Tech Peeps Diaspora — Blog subscribers" group:
  **`192268679358973628`** (account `codedpills@gmail.com`)

Note: MailerLite reviews new accounts before enabling sending/API, and the free
plan caps the list (≈250 subscribers) — fine to start; upgrade when it grows.

### Sending the teaser on publish

`pipeline/teaser.py` builds the email body: the article's opening through the
first `##` heading, closed with "…" and a "Read the full profile →" link, so the
email pulls readers to the site. Preview any published post's teaser with:

```bash
make teaser SLUG=<slug>
```

**Manual trigger.** The workflow also has a `workflow_dispatch` trigger: from the
repo's **Actions → Newsletter on publish → Run workflow**, enter a post `slug`
(the filename in `src/content/blog` without `.md`). Leave **"Send now?" off** to
create a MailerLite **draft** to review; tick it to send immediately. Handy for
sending a post whose auto-run didn't fire (e.g. merged before secrets were set).

**Automatic send on publish.** `.github/workflows/newsletter.yml` runs when a
**newly added** post lands on `main`. It builds the teaser and calls MailerLite's
REST API (`pipeline/send_newsletter.py`) to create a `regular` campaign for the
subscriber group and send it instantly. Editing an existing post does not
re-send (only added files trigger it).

Configure these in **GitHub → repo Settings → Secrets and variables → Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `MAILERLITE_API_KEY` | MailerLite → Integrations → API token |
| Variable | `MAILERLITE_GROUP_ID` | `192268679358973628` |
| Variable | `NEWSLETTER_FROM` | a **verified** sender, e.g. `zak@blog.techpeepsdiaspora.com` |
| Variable | `NEWSLETTER_FROM_NAME` | `Tech Peeps Diaspora` |
| Variable | `SITE_URL` | `https://blog.techpeepsdiaspora.com` |

Because a send is **irreversible**, the PR review is the real gate: by the time a
post merges, the article (and therefore the deterministic teaser) has been
reviewed. To send manually instead — or to test — use the connector in Claude, or
run locally:

```bash
make newsletter SLUG=<slug>          # creates a DRAFT campaign to review
make newsletter SLUG=<slug> SEND=1   # creates AND sends
```

The MailerLite **connector** in Claude remains available for ad-hoc sends and for
inspecting campaigns; the Action is the unattended path.

## Notes

- All source footage is the channel owner's own content; clips and quotes link
  back to the source video.
- **Maintenance:** the site is pinned to Astro 4.x. `npm audit` reports advisories
  in Astro's SSR / dev-server / middleware code paths — this site uses none of
  them (it's fully static, no adapter/middleware), so production exposure is low,
  but plan a staged upgrade to the current Astro major when convenient.
