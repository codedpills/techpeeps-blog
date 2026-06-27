/* Theme toggle — served from /scripts/theme.js (same-origin, CSP script-src 'self').
   Loaded render-blocking in <head> so the saved theme applies before first paint
   (no flash). Default with no saved choice = follow the OS via prefers-color-scheme. */
(function () {
  var root = document.documentElement;

  // 1) Apply any saved override immediately (runs before <body> paints).
  try {
    var saved = localStorage.getItem("theme");
    if (saved === "dark" || saved === "light") {
      root.setAttribute("data-theme", saved);
    }
  } catch (e) {}

  function effectiveTheme() {
    var attr = root.getAttribute("data-theme");
    if (attr === "dark" || attr === "light") return attr;
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function toggle() {
    var next = effectiveTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch (e) {}
  }

  // 2) Delegated click handler — works even though the button parses after this.
  document.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest("#theme-toggle")) toggle();
  });
})();
