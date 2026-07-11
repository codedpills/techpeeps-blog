// Cloudflare Pages Function — POST /api/subscribe
// Same-origin endpoint the newsletter form talks to, so the browser never calls
// MailerLite directly (keeps the site's CSP tight). This runs server-side on
// Cloudflare and forwards the email to MailerLite's API.
//
// Required environment variables (set in Cloudflare Pages → Settings → Env vars,
// as SECRETS — never commit them):
//   MAILERLITE_API_KEY   API token from MailerLite → Integrations → API
//   MAILERLITE_GROUP_ID  (optional) group to add subscribers to
//
// MailerLite: POST https://connect.mailerlite.com/api/subscribers
//   headers: Authorization: Bearer <key>, Content-Type/Accept: application/json
//   body: { email, groups?: [id] }  (upserts; double opt-in handled by MailerLite)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function onRequestPost({ request, env }) {
  if (!env.MAILERLITE_API_KEY) {
    return json({ ok: false, error: "Newsletter is not configured yet." }, 503);
  }

  let data;
  try {
    data = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid request." }, 400);
  }

  // Honeypot: real users leave this empty; bots fill it. Pretend success.
  if (data.hp) return json({ ok: true });

  const email = (data.email || "").toString().trim().toLowerCase();
  if (!EMAIL_RE.test(email)) {
    return json({ ok: false, error: "Please enter a valid email address." }, 422);
  }

  const payload = { email };
  if (env.MAILERLITE_GROUP_ID) payload.groups = [env.MAILERLITE_GROUP_ID];

  let res;
  try {
    res = await fetch("https://connect.mailerlite.com/api/subscribers", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.MAILERLITE_API_KEY}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    return json({ ok: false, error: "Could not reach the newsletter service." }, 502);
  }

  if (res.ok) {
    // MailerLite returns 200/201; with double opt-in on, the subscriber is
    // "unconfirmed" until they click the confirmation email.
    return json({ ok: true });
  }
  if (res.status === 422) {
    return json({ ok: false, error: "Please enter a valid email address." }, 422);
  }
  return json({ ok: false, error: "Something went wrong. Please try again." }, 502);
}
