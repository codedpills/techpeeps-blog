/* Newsletter form — progressive enhancement.
   Served from /scripts/subscribe.js (same-origin, CSP script-src 'self').
   POSTs JSON to /api/subscribe and shows inline status without a page reload.
   If JS is off, the form still submits normally to the Function. */
(function () {
  var form = document.getElementById("newsletter-form");
  if (!form) return;
  var status = document.getElementById("newsletter-status");
  var button = form.querySelector("button[type=submit]");

  function say(msg, kind) {
    if (!status) return;
    status.textContent = msg;
    status.className = "newsletter-status" + (kind ? " is-" + kind : "");
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = (form.email.value || "").trim();
    if (!email) {
      say("Please enter your email address.", "error");
      return;
    }
    button.disabled = true;
    say("Subscribing…", "");

    fetch("/api/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: email, hp: form.hp.value }),
    })
      .then(function (r) {
        return r.json().then(function (b) {
          return { ok: r.ok && b.ok, body: b };
        });
      })
      .then(function (res) {
        if (res.ok) {
          form.reset();
          say("Thanks! Please check your inbox to confirm your subscription.", "success");
        } else {
          say((res.body && res.body.error) || "Something went wrong. Please try again.", "error");
          button.disabled = false;
        }
      })
      .catch(function () {
        say("Network error. Please try again.", "error");
        button.disabled = false;
      });
  });
})();
