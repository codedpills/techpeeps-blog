"""Prompt templates (PRD §9). Shipped as-is.

These are .format()-style templates. Callers fill the named placeholders.
Keep the wording stable — changing it changes article voice and is a
deliberate editorial decision, not a refactor.
"""

# --- §9.1 Feature-profile generation prompt -------------------------------
FEATURE_PROFILE_PROMPT = """\
Role: You are an expert creative non-fiction writer who turns interview
transcripts into polished, narrative-style feature articles — the kind that
profile a guest's ideas with warmth and momentum while keeping every quote
faithful to what was actually said.

Host (interviewer): {host_name} — Tech Peeps Diaspora
Guest: {guest_name}{guest_bio_clause}
Style Guide (host's editorial voice):
{style_guide}

Audience: tech professionals across the diaspora.

Diarized transcript (HOST / GUEST labels, with timestamps):
{transcript}

Instructions:
- Write a narrative feature, NOT a raw Q&A dump. Open with a hook drawn from the
  most striking thing the guest said.
- TITLE: craft a distinctive, curiosity-sparking title built from the single most
  specific or surprising thing in THIS story: a tension, a turning point, a vivid
  detail, or a striking line the guest actually said. It should be impossible to
  swap onto another guest's profile. Do NOT use a generic or templated title, and
  in particular do NOT default to the "From X to Y: Name on Z" formula. Vary the
  shape (a short declarative statement or two often works well). Keep it honest to
  the transcript — intriguing, never clickbait or overstated.
- Use the host's voice for framing, transitions, and reflection; let the guest
  carry the substance.
- Quote the guest ONLY with words that appear verbatim in the transcript, in
  quotation marks. Paraphrase is allowed but must clearly be paraphrase — never
  invent or embellish a quote.
- Do NOT state facts not present in the transcript.
- AVOID the em dash and the double hyphen (the "--" or "—" character) almost
  entirely. Restructure with commas, periods, colons, semicolons, or parentheses
  instead. Only keep a dash in the rare, exceptional case where it is genuinely
  the single best way to make the point land and no other punctuation achieves
  the same effect. Default to zero dashes per article.
- Smooth filler, repetition, and crosstalk. Structure with descriptive H2/H3
  headings.
- Close reflectively, credit and link the guest, and point softly back to the
  video.
- Output valid Markdown with YAML frontmatter matching this schema exactly:
  title, description (<=155 chars), pubDate, guest, guestBio, videoId, videoUrl,
  tags (4-6), heroClip {{mp4, webm, poster, alt}}, draft: true.
  (Leave heroClip paths as placeholders using the slug; they will be filled by
  the clip step.)

After the article, output a section delimited by `<!-- CLIP_CANDIDATES -->` that
is a JSON array of 2-4 candidate hero-clip windows, each:
  {{ "start": "MM:SS", "end": "MM:SS", "reason": "why this moment is compelling" }}
Prefer visually or emotionally striking moments, 3-6 seconds long.
"""

# Stricter retry suffix used when the first generation returns malformed
# frontmatter or no CLIP_CANDIDATES block (PRD §14).
FEATURE_PROFILE_RETRY_SUFFIX = """\

IMPORTANT — your previous output was rejected. You MUST:
1. Begin the response with a YAML frontmatter block delimited by lines containing
   only `---`, with EVERY required key present: title, description, pubDate,
   guest, guestBio, videoId, videoUrl, tags, heroClip (mp4, webm, poster, alt),
   draft.
2. End the response with a line `<!-- CLIP_CANDIDATES -->` followed by a valid
   JSON array of 2-4 objects, each with "start", "end", "reason".
Output nothing before the frontmatter and nothing after the JSON array.
"""


def feature_profile_prompt(
    *,
    host_name: str,
    guest_name: str,
    guest_bio: str | None,
    style_guide: str,
    transcript: str,
) -> str:
    guest_bio_clause = f" — {guest_bio}" if guest_bio else ""
    return FEATURE_PROFILE_PROMPT.format(
        host_name=host_name,
        guest_name=guest_name or "the guest",
        guest_bio_clause=guest_bio_clause,
        style_guide=style_guide,
        transcript=transcript,
    )


# --- §9.3 Style-guide generation prompt (one-time) ------------------------
STYLE_GUIDE_PROMPT = """\
Role: You are an editor analyzing an interviewer's on-air style.

Below are several diarized interview transcripts from the same host
(Tech Peeps Diaspora). Produce a concise, reusable ONE-PAGE style guide
describing the HOST's editorial voice ONLY (not the guests):
- how they set up and frame a guest
- transition style between topics
- humor and warmth markers
- how they open and how they close
- recurring phrasing or signature moves
- a short "never do this" list

Write it so it can be pasted into a blog-writing prompt to keep articles
sounding like this host. Output Markdown.

Transcripts:
{transcripts}
"""


def style_guide_prompt(*, transcripts: str) -> str:
    return STYLE_GUIDE_PROMPT.format(transcripts=transcripts)
