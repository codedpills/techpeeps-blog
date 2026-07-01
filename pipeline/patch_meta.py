#!/usr/bin/env python3
"""patch_meta.py — backfill `interviewDate` into existing PR-branch drafts.

For posts drafted before interviewDate existed, this injects the video's YouTube
publish date (from the transcript's `video_published_at`) into the frontmatter of
the post on its `post/<slug>` branch, committing there — without regenerating the
article (so review edits are preserved). Run `make refresh-meta` first so the
transcripts carry the date.

Each branch is patched in an isolated git worktree, so your current checkout is
untouched. Push the branches afterward to update the PRs.

Usage:
  python pipeline/patch_meta.py --all-drafted
  python pipeline/patch_meta.py <video_id> [<video_id> ...]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import state  # noqa: E402
from lib.config import REPO_ROOT  # noqa: E402

TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                          check=check, capture_output=True, text=True)


def _interview_date(video_id: str) -> str | None:
    p = TRANSCRIPTS_DIR / f"{video_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get("video_published_at")


def _inject(front_md: str, iso_date: str) -> str:
    """Insert or replace `interviewDate:` in a frontmatter markdown file text."""
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)(.*)$", front_md, re.DOTALL)
    if not m:
        raise ValueError("no frontmatter block")
    head, fm, close, body = m.groups()
    if re.search(r"^interviewDate:.*$", fm, re.MULTILINE):
        fm = re.sub(r"^interviewDate:.*$", f"interviewDate: {iso_date}", fm,
                    flags=re.MULTILINE)
    elif re.search(r"^pubDate:.*$", fm, re.MULTILINE):
        fm = re.sub(r"^(pubDate:.*)$", rf"\1\ninterviewDate: {iso_date}", fm,
                    count=1, flags=re.MULTILINE)
    else:
        fm = fm + f"\ninterviewDate: {iso_date}"
    return head + fm + close + body


def patch_branch(video_id: str, slug: str) -> str:
    iso = _interview_date(video_id)
    if not iso:
        return f"skip {video_id}: no video_published_at (run `make refresh-meta`)"
    branch = f"post/{slug}"
    if not _git("rev-parse", "--verify", branch, check=False).returncode == 0:
        return f"skip {video_id}: branch {branch} not found"

    rel = f"src/content/blog/{slug}.md"
    with tempfile.TemporaryDirectory() as tmp:
        _git("worktree", "add", "--quiet", tmp, branch)
        try:
            f = Path(tmp) / rel
            if not f.exists():
                return f"skip {video_id}: {rel} missing on {branch}"
            patched = _inject(f.read_text(encoding="utf-8"), iso)
            f.write_text(patched, encoding="utf-8")
            wt = ["git", "-C", tmp]
            if not subprocess.run(wt + ["diff", "--quiet"]).returncode:
                return f"{video_id}: already up to date (interviewDate {iso})"
            subprocess.run(wt + ["add", rel], check=True)
            subprocess.run(
                wt + ["commit", "-q", "-m", f"Add interviewDate ({iso}) to {slug}"],
                check=True,
            )
            return f"{video_id}: patched interviewDate = {iso} on {branch}"
        finally:
            _git("worktree", "remove", "--force", tmp, check=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill interviewDate on PR branches.")
    ap.add_argument("video_ids", nargs="*")
    ap.add_argument("--all-drafted", action="store_true",
                    help="Patch every video with status 'drafted' and a slug.")
    args = ap.parse_args()

    st = state.load()
    if args.all_drafted:
        targets = [(vid, v["slug"]) for vid, v in st.get("videos", {}).items()
                   if v.get("status") == "drafted" and v.get("slug")]
    else:
        targets = []
        for vid in args.video_ids:
            try:
                targets.append((vid, state.get(st, vid)["slug"]))
            except KeyError:
                print(f"skip {vid}: not in state.json", file=sys.stderr)
    if not targets:
        print("Nothing to patch. Pass <video_id>(s) or --all-drafted.")
        return 1

    for vid, slug in targets:
        if not slug:
            print(f"skip {vid}: no slug")
            continue
        print(" " + patch_branch(vid, slug))
    print("\nPush the patched branches to update their PRs, e.g. `git push origin <branch>`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
