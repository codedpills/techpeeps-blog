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


# Email-safe inline styles (email clients ignore external CSS, so everything is
# inline). Colors mirror the site's "paper" theme; fonts use web-safe stacks.
YOUTUBE_URL = "https://www.youtube.com/@techpeepsdiaspora"
S_P = "margin:0 0 16px;"
S_QUOTE = (
    "border-left:3px solid #b3431f;margin:0 0 20px;padding:4px 0 4px 16px;"
    "font-style:italic;color:#423d34;font-size:19px;line-height:1.5;"
)
S_LINK = "color:#b3431f;"


def md_inline_to_html(text: str) -> str:
    """Minimal, safe Markdown -> HTML for teaser paragraphs, with inline styles
    so it renders correctly in email clients (no external CSS). Handles
    **bold**, *italic*, [links](url), and blockquotes; splits paragraphs.
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
        esc = re.sub(
            r"\[([^\]]+)\]\((https?://[^)]+)\)",
            rf'<a href="\2" style="{S_LINK}">\1</a>',
            esc,
        )
        esc = esc.replace("\n", "<br>")
        if is_quote:
            html_blocks.append(f'<blockquote style="{S_QUOTE}">{esc}</blockquote>')
        else:
            html_blocks.append(f'<p style="{S_P}">{esc}</p>')
    return "\n".join(html_blocks)


def build_teaser(path: Path, site: str, from_email: str = "") -> dict:
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    slug = path.stem
    site = site.rstrip("/")
    url = f"{site}/blog/{slug}/"
    opening_html = md_inline_to_html(body_before_first_h2(body))
    title = str(fm.get("title", slug))
    guest = fm.get("guest", "")

    # Gentle "add me to contacts" nudge — the most reliable way to keep future
    # sends out of Gmail's Promotions tab (per-recipient training).
    contact = html_lib.escape(from_email) if from_email else "this address"
    ps = (
        f'<p style="font-family:Arial,Helvetica,sans-serif;font-size:12px;'
        f'color:#8a8378;margin:10px 0 0;">P.S. So the next profile reaches you, '
        f"add {contact} to your contacts and move this email to your Primary tab.</p>\n"
    )

    body_html = (
        f'<div style="max-width:600px;margin:0 auto;padding:24px 20px;'
        f"font-family:Georgia,'Times New Roman',serif;color:#23201a;"
        f'font-size:17px;line-height:1.65;">\n'
        f'<h1 style="font-size:26px;line-height:1.22;font-weight:700;'
        f'color:#16140f;margin:0 0 18px;">{html_lib.escape(title)}</h1>\n'
        f"{opening_html}\n"
        f'<p style="color:#8a8378;margin:0 0 8px;">&hellip;</p>\n'
        f'<p style="margin:22px 0 0;"><a href="{url}" '
        f'style="color:#b3431f;font-weight:700;text-decoration:none;">'
        f"Read the full profile &rarr;</a></p>\n"
        f'<hr style="border:none;border-top:1px solid #e3ddce;margin:28px 0 16px;">\n'
        f'<p style="font-family:Arial,Helvetica,sans-serif;font-size:13px;'
        f'color:#6d665a;margin:0;">A profile from '
        f'<a href="{site}" style="{S_LINK}">Tech Peeps Diaspora</a>, tech stories '
        f'from across the diaspora. '
        f'<a href="{YOUTUBE_URL}" style="{S_LINK}">Watch the interviews on '
        f"YouTube &rarr;</a></p>\n"
        f"{ps}"
        f"</div>"
    )
    # Subject is the article title, per editorial preference.
    return {"subject": title, "html": body_html, "url": url, "title": title, "guest": guest}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a newsletter teaser from a post.")
    ap.add_argument("post")
    ap.add_argument("--site", default=os.environ.get("SITE_URL", "https://techpeeps.example.com"))
    ap.add_argument("--from", dest="from_email", default=os.environ.get("NEWSLETTER_FROM", ""))
    ap.add_argument("--json", action="store_true", help="Emit JSON (subject+html+url).")
    args = ap.parse_args()

    p = Path(args.post)
    if not p.exists():
        print(f"ERROR: not found: {p}", file=sys.stderr)
        return 1
    t = build_teaser(p, args.site, args.from_email)
    if args.json:
        print(json.dumps(t, ensure_ascii=False, indent=2))
    else:
        print(f"SUBJECT: {t['subject']}\nURL: {t['url']}\n\n{t['html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
