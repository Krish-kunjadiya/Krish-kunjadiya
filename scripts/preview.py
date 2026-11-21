#!/usr/bin/env python3
"""Preview the profile README locally before pushing.

    python scripts/preview.py        then open http://localhost:8765

Every page refresh re-renders the cards from profile.json and the saved data, so
you can edit, refresh and see the result. It never commits, pushes or fetches.
"""
import re
import subprocess
import sys
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
RENDER = ROOT / "scripts" / "render_cards.py"

PAGE ="""<!doctype html>
<html lang="en" data-theme="dark" data-view="desktop">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Profile preview</title>
<base target="_blank">
<style>
html[data-theme=dark]{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#3d444d;--link:#4493f8;--button:#212830;color-scheme:dark}
html[data-theme=light]{--bg:#fff;--fg:#1f2328;--muted:#59636e;--line:#d1d9e0;--link:#0969da;--button:#f6f8fa;color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header{position:sticky;top:0;z-index:1;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px;background:var(--bg);border-bottom:1px solid var(--line)}
header strong{margin-right:auto}
button{min-height:32px;padding:4px 12px;border:1px solid var(--line);border-radius:6px;background:var(--button);color:var(--fg);font:inherit;cursor:pointer}
button[aria-pressed=true]{border-color:#FA4400;box-shadow:inset 0 0 0 1px #FA4400}
button:focus-visible{outline:2px solid #FA4400;outline-offset:2px}
main{width:100%;max-width:840px;margin:24px auto;border:1px solid var(--line);border-radius:6px}
html[data-view=mobile] main{max-width:390px}
.file{padding:8px 16px;border-bottom:1px solid var(--line);color:var(--muted);font-weight:600}
article{padding:32px;font-size:16px}
html[data-view=mobile] article{padding:16px}
article img{max-width:100%;border-style:none}
article a{color:var(--link)}
article p{margin:16px 0 0}
</style>
</head>
<body>
<header>
<strong>Local preview, not on GitHub yet</strong>
<button data-theme-choice="dark">Dark</button>
<button data-theme-choice="light">Light</button>
<button data-view-choice="desktop">Desktop</button>
<button data-view-choice="mobile">Mobile</button>
<button id="replay">Replay animation</button>
</header>
<main><div class="file">README.md</div><article>__README__</article></main>
<script>
const root = document.documentElement;
const saved = JSON.parse(sessionStorage.getItem("preview") || "{}");
function apply(theme, view) {
  root.dataset.theme = theme;
  root.dataset.view = view;
  sessionStorage.setItem("preview", JSON.stringify({ theme, view }));
  document.querySelectorAll("picture source").forEach((source) => {
    source.media = theme === "dark" ? "all" : "not all";
  });
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.themeChoice === theme);
  });
  document.querySelectorAll("[data-view-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.viewChoice === view);
  });
}
document.querySelectorAll("[data-theme-choice]").forEach((button) => {
  button.onclick = () => apply(button.dataset.themeChoice, root.dataset.view);
});
document.querySelectorAll("[data-view-choice]").forEach((button) => {
  button.onclick = () => apply(root.dataset.theme, button.dataset.viewChoice);
});
document.getElementById("replay").onclick = () => location.reload();
apply(saved.theme || "dark", saved.view || "desktop");
</script>
</body>
</html>
"""


class Preview(BaseHTTPRequestHandler):
    def send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            result = subprocess.run([sys.executable, str(RENDER)], capture_output=True, text=True)
            if result.returncode:
                message = f"<h1>Could not render the cards</h1><pre>{escape(result.stderr)}</pre>"
                self.send(500, "text/html; charset=utf-8", message.encode("utf-8"))
                return
            readme = (ROOT / "README.md").read_text(encoding="utf-8")
            self.send(200, "text/html; charset=utf-8", PAGE.replace("__README__", readme).encode("utf-8"))
            return
        match = re.fullmatch(r"/cards/([\w.-]+\.svg)", path)
        card = CARDS / match.group(1) if match else None
        if card and card.is_file():
            self.send(200, "image/svg+xml", card.read_bytes())
        else:
            self.send(404, "text/plain; charset=utf-8", b"Not found")

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Preview)
    print(f"Preview running at http://localhost:{port} (press Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
