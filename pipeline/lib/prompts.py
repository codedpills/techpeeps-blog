"""Prompt templates (PRD §9). Shipped as-is.

These are .format()-style templates. Callers fill the named placeholders.
Keep the wording stable — changing it changes article voice and is a
deliberate editorial decision, not a refactor.
"""

# Anti-"AI slop" guidance, adapted from an editing checklist for our
# generate-first use case: instead of fixing slop after the fact, write without
# it the first time. CRITICAL: every rule below governs ONLY the narrative prose
# you write (framing, transitions, reflection). It NEVER applies to the guest's
# words inside quotation marks, which must stay VERBATIM even if they contain a
# "banned" word or phrase.
ANTI_SLOP_GUIDE = """\
Write like a sharp human, not an AI. These rules apply to YOUR prose only, never
to the guest's verbatim quotes:

Substance and voice
- Lead with the point. Cut generic throat-clearing openers ("Here's the thing",
  "Let me be clear", "The uncomfortable truth is"). Keep a personal aside or
  admission only when it adds real context, tension, or character.
- Be concrete and specific. Names, numbers, dates, mechanisms, and real examples
  from the transcript beat abstractions. Never smooth a specific detail into
  generic importance ("significantly improved efficiency").
- Use active voice and direct verbs: "decided", not "made a decision"; "can",
  not "has the ability to". Never let an inanimate thing perform a human verb.
- Vary sentence and paragraph shape. Avoid repeated structures, robotic rhythm,
  and stacked one-line fragments for drama.

Words to avoid in your prose: delve, foster, leverage, utilize, facilitate,
empower, streamline, robust, cutting-edge, paradigm shift, game changer, tapestry,
realm, beacon, multifaceted, meticulous, intricate, paramount, transformative,
elevate, embark, supercharge, harness, ever-evolving. Trim empty adverbs (just,
really, actually, literally, simply, fundamentally, importantly) unless they
carry genuine emphasis or uncertainty.

Empty phrases to avoid: "it's worth noting", "it's important to note", "at the end
of the day", "when it comes to", "at its core", "in today's world", "in the age
of", "the reality is", "the truth is", "in order to", "in this article", "let's
dive in".

Patterns to avoid
- Binary contrasts ("It's not X, it's Y", "The question isn't X, it's Y"): state
  Y directly.
- Faux-insight setups ("what most people miss", "here's what nobody tells you"):
  let the claim stand on its own.
- Colon reveals (a noun phrase, a colon, then a dramatic lowercase reveal): write
  a plain sentence. Use colons only for lists, labels, or quotes.
- Superficial "-ing" analysis ("highlighting", "underscoring", "reflecting",
  "showcasing"): state the concrete consequence instead.
- Importance puffery ("marks a pivotal moment", "stands as a testament", "plays a
  vital role"): state the fact and let the reader judge.
- Weasel attribution ("experts agree", "studies show"): only claim what the
  transcript supports; never invent a source.
- Synonym cycling: repeat the clear word rather than rotating terms for style.
- Rhetorical setups ("What if I told you", "Think about it:", "Plot twist:"):
  just make the point.
- Fake-profound kickers and summary-recap endings ("In conclusion", "Ultimately",
  "Overall"): end on the clearest concrete point or a plain takeaway, not a
  mic-drop metaphor or a restatement of what the reader just read.

Formatting: no emoji in headings, no mid-sentence bold for emphasis, no bullet
lists where two sentences of prose read better, no headers over two-sentence
sections. Let the format follow the content."""


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
  most striking thing the guest said, if it can be quoted verbatim. Otherwise, 
  open with a vivid scene or a concrete detail from the transcript. Avoid generic 
  or abstract openers.
- TITLE: craft a distinctive, curiosity-sparking title built from the single most
  specific or surprising thing in THIS story: a tension, a turning point, a vivid
  detail, or a striking line the guest actually said. It should be impossible to
  swap onto another guest's profile. Do NOT use a generic or templated title, and
  in particular do NOT default to the "From X to Y: Name on Z" formula. Vary the
  shape (a short declarative statement or two often works well). Keep it honest to
  the transcript — intriguing, never clickbait or overstated.
- Use the host's voice for framing, transitions, and reflection; let the guest
  carry the substance. Do not refer to the host in the third person.
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
- Write the narrative prose to avoid AI "slop". Follow this guidance, which
  applies to your own prose ONLY and never to the guest's verbatim quotes:
{anti_slop}
- Close on a concrete, human note and point softly back to the video. Do NOT end
  with a summary recap or a "deep" mic-drop aphorism; credit and link the guest.
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
        anti_slop=ANTI_SLOP_GUIDE,
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
