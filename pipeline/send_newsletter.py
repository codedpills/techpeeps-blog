#!/usr/bin/env python3
"""send_newsletter.py — create (and optionally send) a MailerLite campaign for a
published post, via the REST API. Used by the on-publish GitHub Action.

Builds the teaser (pipeline/teaser.py), creates a "regular" campaign targeting
the subscriber group, and — with --send — schedules it for instant delivery.
Default is DRAFT (safe for local runs); the Action passes --send.

Environment:
  MAILERLITE_API_KEY     (required) API token
  MAILERLITE_GROUP_ID    (required) target subscriber group id
  NEWSLETTER_FROM        (required) verified sender email
  NEWSLETTER_FROM_NAME   sender name (default "Tech Peeps Diaspora")
  SITE_URL               site origin for the read-more link

Usage:
  python pipeline/send_newsletter.py <post.md> [--send] [--site URL]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import teaser  # noqa: E402

API = "https://connect.mailerlite.com/api"


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"ERROR: {name} is not set.", file=sys.stderr)
        raise SystemExit(2)
    return val


def create_campaign(session: requests.Session, *, name, subject, from_name,
                    from_email, html, group_id) -> str:
    payload = {
        "name": name,
        "type": "regular",
        "emails": [
            {
                "subject": subject,
                "from_name": from_name,
                "from": from_email,
                "content": html,
            }
        ],
        "groups": [group_id],
    }
    r = session.post(f"{API}/campaigns", json=payload, timeout=60)
    if not r.ok:
        raise RuntimeError(f"create campaign failed ({r.status_code}): {r.text}")
    cid = r.json().get("data", {}).get("id") or r.json().get("id")
    if not cid:
        raise RuntimeError(f"create campaign: no id in response: {r.text}")
    return str(cid)


def schedule_instant(session: requests.Session, campaign_id: str) -> None:
    r = session.post(
        f"{API}/campaigns/{campaign_id}/schedule",
        json={"delivery": "instant"},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"schedule failed ({r.status_code}): {r.text}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Create/send a MailerLite campaign for a post.")
    ap.add_argument("post")
    ap.add_argument("--send", action="store_true",
                    help="Send immediately (delivery=instant). Default: leave as draft.")
    ap.add_argument("--site", default=os.environ.get("SITE_URL", ""))
    args = ap.parse_args()

    post = Path(args.post)
    if not post.exists():
        print(f"ERROR: post not found: {post}", file=sys.stderr)
        return 1

    api_key = _require("MAILERLITE_API_KEY")
    group_id = _require("MAILERLITE_GROUP_ID")
    from_email = _require("NEWSLETTER_FROM")
    from_name = os.environ.get("NEWSLETTER_FROM_NAME", "Tech Peeps Diaspora")
    site = args.site or "https://techpeeps.example.com"

    t = teaser.build_teaser(post, site)

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })

    try:
        cid = create_campaign(
            session,
            name=t["title"][:120],
            subject=t["subject"],
            from_name=from_name,
            from_email=from_email,
            html=t["html"],
            group_id=group_id,
        )
        print(f"Created campaign {cid} for {post.name}")
        if args.send:
            schedule_instant(session, cid)
            print(f"Sent campaign {cid} (instant) to group {group_id}")
        else:
            print("Left as DRAFT (pass --send to deliver).")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
