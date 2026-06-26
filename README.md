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
(`gh`)** authenticated (`gh auth login`) or a `GITHUB_TOKEN`. `yt-dlp` installs
via pip.

```bash
cp .env.example .env        # then fill in real values
make install                # pip + npm install
```

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

## The site

Astro static site with a `blog` content collection validated by
`src/content/config.ts` (zod). A malformed draft **fails the build**. Hero clips
render as `<video autoplay loop muted playsinline>` with a poster fallback, so
they read like GIFs but stay small and sharp.

```bash
make site-dev      # local dev server
make site-build    # production build (fails on invalid frontmatter)
```

Hosting: push `main` to Cloudflare Pages or Netlify (free tier) for git-push
auto-deploy.

## Notes

- An example post (`src/content/blog/example-profile.md`) and its placeholder
  clip assets ship with the repo so the site builds out of the box. **Delete
  them before going live.**
- All source footage is the channel owner's own content; clips and quotes link
  back to the source video.
