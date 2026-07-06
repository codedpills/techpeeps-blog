#!/usr/bin/env python3
"""teaser.py — build the newsletter teaser for a published post.

The teaser is the article's opening: everything from the start of the body up to
(but not including) the first "## " section heading, closed with an ellipsis and
a "Read the full profile" link back to the site. This is what the email contains,
enticing the reader to click through to the blog for the rest.

Outputs both HTML (for an email campaign body) and the subject line. Reused by
the send step; also runnable standalone to preview.

Usage:
  python pipeline/teaser.py <path-to-post.md> [--site https://yourdomain]
  python pipeline/teaser.py <path-to-post.md> --json
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required: pip install PyYAML", file=sys.stderr)
    raise


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError("no YAML frontmatter found")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def body_before_first_h2(body: str) -> str:
    """Return body text up to the first '## ' heading (the end of the opening)."""
    lines = body.splitlines()
    out: list[str] = []
    for line in lines:
        if re.match(r"^##\s+", line):  # first H2 -> stop
            break
        out.append(line)
    # Drop a leading H1 (the article repeats the title) and horizontal rules.
    out = [
        ln for ln in out
        if not re.match(r"^#\s+", ln) and not re.match(r"^\s*([-*_])\1{2,}\s*$", ln)
    ]
    return "\n".join(out).strip()


def md_inline_to_html(text: str) -> str:
    """Minimal, safe Markdown -> HTML for teaser paragraphs: escapes HTML, then
    renders **bold**, *italic*, [links](url), and blockquotes; splits paragraphs.
    Kept deliberately small (no external renderer) since teasers are simple prose.
    """
    blocks = re.split(r"\n\s*\n", text.strip())
    html_blocks: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        is_quote = block.startswith(">")
        if is_quote:
            block = re.sub(r"^>\s?", "", block, flags=re.MULTILINE)
        esc = html_lib.escape(block)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", esc)
        esc = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', esc)
        esc = esc.replace("\n", "<br>")
        html_blocks.append(f"<blockquote>{esc}</blockquote>" if is_quote else f"<p>{esc}</p>")
    return "\n".join(html_blocks)


def build_teaser(path: Path, site: str) -> dict:
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    slug = path.stem
    url = f"{site.rstrip('/')}/blog/{slug}/"
    opening = body_before_first_h2(body)
    opening_html = md_inline_to_html(opening)
    title = fm.get("title", slug)
    guest = fm.get("guest", "")

    read_more = (
        f'<p><a href="{url}"><strong>Read the full profile &rarr;</strong></a></p>'
    )
    html = (
        f"<h1>{html_lib.escape(str(title))}</h1>\n"
        f"{opening_html}\n"
        f'<p style="color:#6d665a">&hellip;</p>\n'
        f"{read_more}"
    )
    subject = f"New profile: {guest}" if guest else f"New: {title}"
    return {"subject": subject, "html": html, "url": url, "title": title, "guest": guest}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a newsletter teaser from a post.")
    ap.add_argument("post")
    ap.add_argument("--site", default=os.environ.get("SITE_URL", "https://techpeeps.example.com"))
    ap.add_argument("--json", action="store_true", help="Emit JSON (subject+html+url).")
    args = ap.parse_args()

    p = Path(args.post)
    if not p.exists():
        print(f"ERROR: not found: {p}", file=sys.stderr)
        return 1
    t = build_teaser(p, args.site)
    if args.json:
        print(json.dumps(t, ensure_ascii=False, indent=2))
    else:
        print(f"SUBJECT: {t['subject']}\nURL: {t['url']}\n\n{t['html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
