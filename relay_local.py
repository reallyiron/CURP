import json
import threading
import sys
import time
import socket
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# pytchat is only needed for the YouTube side. Guard the import so that a
# missing/broken pytchat does NOT prevent the web server from starting — the
# overlay should still load (showing "offline") so you can see it's alive.
try:
    import pytchat
    PYTCHAT_OK = True
    PYTCHAT_ERR = ""
except Exception as _e:
    pytchat = None
    PYTCHAT_OK = False
    PYTCHAT_ERR = str(_e)

PORT = 8080
all_messages = []
msg_lock = threading.Lock()
chat_alive = False
video_id_global = ""
last_error = ""        # human-readable reason the chat is offline (shown in JSON)

# ── HTML OVERLAY ─────────────────────────────────────────────────────────────
# Open in OBS browser source at any resolution.
# Add  ?obs  to the URL for a transparent background with no chrome.
# ─────────────────────────────────────────────────────────────────────────────
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>IRONCONTROL Chat</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d0d0f;
  --surface:#141418;
  --border:rgba(255,255,255,.07);
  --text:#efeff1;
  --muted:#9898a8;
  --cmd-bg:rgba(145,70,255,.08);
  --cmd-bar:#9146ff;
  --mod:#00e5a0;
  --own:#f8b500;
  --live:#00e5a0;
  --dead:#ef4444;
}
html,body{width:100%;height:100%;background:var(--bg);color:var(--text);
  font-family:'Inter',system-ui,-apple-system,sans-serif;font-size:13px;
  overflow:hidden;-webkit-font-smoothing:antialiased}
body.obs{background:transparent!important}

/* ── HEADER (hidden in OBS mode) ───────────────────────────────────────── */
#hdr{
  position:fixed;top:0;left:0;right:0;z-index:20;height:40px;
  background:var(--surface);border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:10px;padding:0 16px;
  -webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);
}
body.obs #hdr{display:none}

#live-dot{
  width:8px;height:8px;border-radius:50%;background:var(--live);
  flex-shrink:0;animation:breathe 2.2s ease-in-out infinite;
}
#live-dot.dead{background:var(--dead);animation:none}

#hdr-title{
  font-size:11px;font-weight:700;letter-spacing:2px;
  color:var(--text);text-transform:uppercase
}
#hdr-vid{font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#hdr-right{
  margin-left:auto;font-size:11px;color:var(--muted);
  display:flex;align-items:center;gap:14px;flex-shrink:0
}

/* ── CHAT FEED ──────────────────────────────────────────────────────────── */
#feed{
  position:fixed;top:40px;bottom:30px;left:0;right:0;
  overflow-y:auto;overflow-x:hidden;
  display:flex;flex-direction:column;justify-content:flex-end;
  padding:4px 0;
}
body.obs #feed{top:0;bottom:0}
#feed::-webkit-scrollbar{width:0}

/* ── MESSAGES ───────────────────────────────────────────────────────────── */
.msg{
  display:flex;align-items:baseline;gap:5px;
  padding:3px 16px;border-radius:2px;line-height:1.65;
  animation:rise .16s cubic-bezier(.4,0,.2,1) both;
  flex-shrink:0;min-width:0;
}
.msg:hover{background:rgba(255,255,255,.04)}

.msg.cmd{
  border-left:2.5px solid var(--cmd-bar);
  padding-left:13px;background:var(--cmd-bg);
}
.msg.cmd:hover{background:rgba(145,70,255,.14)}

/* Badges */
.bw{display:flex;gap:3px;align-self:center;flex-shrink:0;margin-right:1px}
.bdg{
  font-size:8px;font-weight:700;letter-spacing:.3px;padding:1px 5px;
  border-radius:2px;line-height:1.6;white-space:nowrap
}
.bdg.mod{background:rgba(0,229,160,.14);color:var(--mod);border:1px solid rgba(0,229,160,.3)}
.bdg.own{background:rgba(248,181,0,.14);color:var(--own);border:1px solid rgba(248,181,0,.3)}

.name{font-weight:600;white-space:nowrap;flex-shrink:0;cursor:default}
.sep{color:var(--muted);flex-shrink:0;user-select:none;margin-right:3px}
.txt{color:var(--muted);word-break:break-word;min-width:0}
.msg.cmd .txt{color:var(--text)}

/* ── STATUS BAR (hidden in OBS mode) ───────────────────────────────────── */
#bar{
  position:fixed;bottom:0;left:0;right:0;height:30px;
  background:var(--surface);border-top:1px solid var(--border);
  display:flex;align-items:center;gap:20px;padding:0 16px;
  font-size:10px;color:var(--muted);
}
body.obs #bar{display:none}
#bar b{color:var(--text);font-weight:600}
#bar .dot{
  width:6px;height:6px;border-radius:50%;
  background:var(--live);flex-shrink:0;
}
#bar .dot.dead{background:var(--dead)}

/* ── ANIMATIONS ─────────────────────────────────────────────────────────── */
@keyframes breathe{
  0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(0,229,160,.45)}
  50%    {opacity:.5;box-shadow:0 0 0 5px rgba(0,229,160,0)}
}
@keyframes rise{
  from{opacity:0;transform:translateY(6px)}
  to  {opacity:1;transform:translateY(0)}
}
</style>
</head>
<body>
<!-- HEADER -->
<div id="hdr">
  <div id="live-dot"></div>
  <span id="hdr-title">IRONCONTROL</span>
  <span id="hdr-vid"></span>
  <span id="hdr-right">
    <span id="h-count">0 msgs</span>
  </span>
</div>

<!-- CHAT FEED -->
<div id="feed"></div>

<!-- STATUS BAR -->
<div id="bar">
  <div class="dot" id="b-dot"></div>
  <span>STATUS&nbsp;<b id="b-status">connecting…</b></span>
  <span>MSGS&nbsp;<b id="b-count">0</b></span>
</div>

<script>
(function () {
  'use strict';

  // ── CONFIG ──────────────────────────────────────────────────────────────
  var MAX   = 100;   // max messages displayed before pruning old ones
  var POLL  = 50;    // polling interval in ms (50ms = near-instant feel)

  // Twitch-style username colour palette
  var COLS = [
    '#ff4500','#2e8b57','#daa520','#9146ff','#1e90ff',
    '#ff69b4','#00bfff','#ff6347','#7cfc00','#ffa500',
    '#dc143c','#9932cc','#00ced1','#ff8c00','#adff2f'
  ];

  // ── STATE ───────────────────────────────────────────────────────────────
  var cursor    = 0;
  var atBottom  = true;

  // OBS mode: add ?obs to browser source URL for transparent bg + no chrome
  if (/[?&]obs/.test(location.search)) document.body.classList.add('obs');

  // ── DOM REFS ────────────────────────────────────────────────────────────
  var feed    = document.getElementById('feed');
  var liveDot = document.getElementById('live-dot');
  var hdrVid  = document.getElementById('hdr-vid');
  var hCount  = document.getElementById('h-count');
  var bDot    = document.getElementById('b-dot');
  var bStatus = document.getElementById('b-status');
  var bCount  = document.getElementById('b-count');

  // ── HELPERS ─────────────────────────────────────────────────────────────
  function hue(name) {
    var h = 0;
    for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return COLS[h % COLS.length];
  }

  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ── AUTO-SCROLL ─────────────────────────────────────────────────────────
  feed.addEventListener('scroll', function () {
    atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 70;
  });

  // ── RENDER A MESSAGE ────────────────────────────────────────────────────
  function appendMsg(m) {
    var isCmd = m.text && m.text.charAt(0) === '!';
    var div   = document.createElement('div');
    div.className = 'msg' + (isCmd ? ' cmd' : '');

    var bdgs = '';
    if (m.isOwner)     bdgs = '<span class="bw"><span class="bdg own">OWNER</span></span>';
    else if (m.isMod)  bdgs = '<span class="bw"><span class="bdg mod">MOD</span></span>';

    div.innerHTML =
      bdgs +
      '<span class="name" style="color:' + hue(m.author) + '">' + esc(m.author) + '</span>' +
      '<span class="sep">:</span>' +
      '<span class="txt">'  + esc(m.text)   + '</span>';

    feed.appendChild(div);
  }

  // ── PRUNE OLD MESSAGES ──────────────────────────────────────────────────
  function prune() {
    var kids = feed.children;
    while (kids.length > MAX) feed.removeChild(kids[0]);
  }

  // ── SET LIVE / DEAD INDICATORS ──────────────────────────────────────────
  function setAlive(alive) {
    liveDot.className = alive ? '' : 'dead';
    bDot.className    = 'dot' + (alive ? '' : ' dead');
    bStatus.textContent = alive ? 'live' : 'offline';
  }

  // ── POLL LOOP ────────────────────────────────────────────────────────────
  function poll() {
    fetch('/chat?after=' + cursor + '&_=' + Date.now())
      .then(function (r) { return r.json(); })
      .then(function (d) {
        setAlive(!!d.alive);

        if (d.messages && d.messages.length) {
          var snap = atBottom;
          for (var i = 0; i < d.messages.length; i++) appendMsg(d.messages[i]);
          prune();
          cursor       = d.total;
          var label    = cursor + ' msgs';
          hCount.textContent = label;
          bCount.textContent = cursor;
          if (snap) feed.scrollTop = feed.scrollHeight;
        }
      })
      .catch(function () { setAlive(false); })
      .finally(function () { setTimeout(poll, POLL); });
  }

  // Fetch video id for header decoration
  fetch('/status')
    .then(function (r) { return r.json(); })
    .then(function (d) { if (d.video) hdrVid.textContent = '· ' + d.video; })
    .catch(function () {});

  poll();
}());
</script>
</body>
</html>"""
# ─────────────────────────────────────────────────────────────────────────────


class RelayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/":
            try:
                payload = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
            except Exception:
                pass
            return

        if parsed.path == "/chat":
            after = int(params.get("after", ["0"])[0])
            with msg_lock:
                msgs  = all_messages[after:]
                total = len(all_messages)
            body = json.dumps({"messages": msgs, "total": total,
                               "alive": chat_alive, "error": last_error})

        elif parsed.path == "/status":
            with msg_lock:
                total = len(all_messages)
            body = json.dumps({
                "alive":      chat_alive,
                "video":      video_id_global,
                "total_msgs": total,
                "error":      last_error,
                "relay":      "ironcontrol",   # ← scanner looks for this field
            })
        else:
            body = json.dumps({
                "relay":     "ironcontrol",
                "endpoints": ["/", "/chat?after=N", "/status"],
            })

        try:
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            pass

    def log_message(self, format, *args):
        pass  # suppress per-request logging


class ReuseHTTPServer(ThreadingHTTPServer):
    """Threaded so the overlay's fast polling, the dashboard, and the Pico can
    all hit the server at once without blocking each other. allow_reuse_address
    avoids 'address already in use' from a lingering TIME_WAIT socket on restart."""
    allow_reuse_address = True
    daemon_threads = True


def make_server():
    """Bind the HTTP server, trying a few ports if 8080 is taken.
    Returns (server, port). Raises if nothing could bind."""
    global PORT
    last_err = None
    for candidate in (PORT, 8081, 8088, 8090, 8000):
        try:
            srv = ReuseHTTPServer(("0.0.0.0", candidate), RelayHandler)
            PORT = candidate
            return srv
        except OSError as e:
            last_err = e
            print(f"  port {candidate} unavailable ({e}); trying next…")
    raise last_err


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def extract_video_id(raw):
    """Accept a bare ID or any YouTube URL form and return the 11-char video ID.
    Handles watch?v=, youtu.be/, /live/, /embed/, and extra query params."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    # Already a bare-ish ID (no slashes, no scheme)
    if "/" not in raw and "?" not in raw and "&" not in raw:
        return raw
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(raw if "//" in raw else "https://" + raw)
        # watch?v=ID
        q = parse_qs(u.query)
        if "v" in q and q["v"]:
            return q["v"][0]
        # youtu.be/ID  or  /live/ID  or  /embed/ID
        seg = [s for s in u.path.split("/") if s]
        if seg:
            cand = seg[-1]
            # strip any trailing params just in case
            return cand.split("?")[0].split("&")[0]
    except Exception:
        pass
    return raw


def run_chat(video_id):
    """Read YouTube chat into all_messages. Auto-reconnects with backoff.

    Note: YouTube's live-chat API delivers messages in batches every 1-5 s.
    That delay is inherent to YouTube — this relay adds zero extra latency.

    IMPORTANT: pytchat only works on a stream that is LIVE *right now*
    (not 'upcoming', not a finished VOD/premiere). If you see alive:false,
    the reason is now reported in /status and /chat as the "error" field.
    """
    global chat_alive, last_error
    backoff = 5

    while True:
        try:
            print(f" Connecting to YouTube chat for video: {video_id}")
            last_error = "connecting..."
            chat = pytchat.create(video_id=video_id)

            # pytchat creates fine even for a non-live video; confirm it's actually live.
            if not chat.is_alive():
                # Pull the underlying reason if pytchat exposes one
                reason = ""
                try:
                    chat.raise_for_status()
                except Exception as re:
                    reason = str(re) or type(re).__name__
                last_error = "stream not live / no live chat" + (f" ({reason})" if reason else "")
                chat_alive = False
                print(f" {last_error}")
                print(f" Reconnecting in {backoff}s…  (is the stream LIVE right now?)")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

            chat_alive = True
            last_error = ""
            backoff = 5
            print(f" Connected! Open http://localhost:{PORT} to see the overlay.")

            while chat.is_alive():
                try:
                    for c in chat.get().sync_items():
                        with msg_lock:
                            all_messages.append({
                                "author":  c.author.name,
                                "text":    c.message,
                                "isMod":   c.author.isChatModerator,
                                "isOwner": c.author.isChatOwner,
                            })
                            idx = len(all_messages)
                        print(f" [{idx}] {c.author.name}: {c.message}")
                except Exception as ie:
                    # Don't silently swallow — record it so you can see it.
                    last_error = f"read error: {ie}"
                    print(f" {last_error}")
                    break   # drop out and let the outer loop reconnect

            # Chat ended or we broke out
            try:
                chat.raise_for_status()
            except Exception as re:
                last_error = str(re) or type(re).__name__
            if not last_error:
                last_error = "chat ended"

        except KeyboardInterrupt:
            print("\n Stopped by user.")
            chat_alive = False
            break
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f" Chat error: {last_error}")

        chat_alive = False
        print(f" Reconnecting in {backoff}s…")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def main():
    global video_id_global

    # 1. Try reading video_id from state.json
    try:
        with open("state.json", "r") as f:
            data = json.load(f)
            video_id_global = data.get("video_id", "")
    except Exception:
        pass

    # 2. Command-line argument overrides state.json
    if len(sys.argv) >= 2:
        video_id_global = sys.argv[1]

    # Accept a full YouTube URL or a bare ID — normalize to the 11-char ID.
    raw_in = video_id_global
    video_id_global = extract_video_id(video_id_global)
    if raw_in and raw_in != video_id_global:
        print(f"  (interpreted '{raw_in}' as video id '{video_id_global}')")

    # ---- Start the web server FIRST, before anything that can fail/block. ----
    # This way localhost:PORT is reachable immediately, and a bind failure is
    # reported loudly instead of dying silently inside a daemon thread.
    try:
        server = make_server()
    except OSError as e:
        print("=" * 52)
        print("  FATAL: could not start the web server.")
        print(f"  {e}")
        print("  Likely another copy of relay_local.py is still running,")
        print("  or another app is using the port. Close it and retry,")
        print("  or change PORT at the top of this file.")
        print("=" * 52)
        sys.exit(1)

    threading.Thread(target=server.serve_forever, daemon=True).start()

    local_ip = get_local_ip()
    print("=" * 52)
    print("  IRONCONTROL — pytchat Relay + OBS Chat Overlay")
    print("=" * 52)
    print(f"  HTTP server LIVE on 0.0.0.0:{PORT}")
    print(f"  OVERLAY    =  http://localhost:{PORT}/")
    print(f"  OBS URL    =  http://localhost:{PORT}/?obs")
    print(f"  STATUS     =  http://localhost:{PORT}/status")
    print(f"  RELAY_URL  =  \"http://{local_ip}:{PORT}/chat\"")
    print("=" * 52)
    print("  Put RELAY_URL in Pico settings.toml OR leave it")
    print("  empty — the Pico will auto-scan the LAN for it.")
    print("  YouTube batches chat every ~1-5 s (API limit).")
    print("=" * 52)

    # ---- Now bring up the YouTube side (the overlay already works without it) ----
    if not PYTCHAT_OK:
        print("  WARNING: pytchat failed to import — overlay is up but no chat.")
        print(f"  ({PYTCHAT_ERR})")
        print("  Install it with:  pip install pytchat")
    elif not video_id_global:
        print("  WARNING: no VIDEO_ID — overlay is up but not reading chat.")
        print("  Pass one:  python relay_local.py <VIDEO_ID>")
        print("  or create state.json → { \"video_id\": \"VIDEO_ID\" }")
    else:
        try:
            run_chat(video_id_global)
        except KeyboardInterrupt:
            pass
        print(" Relay stopped.")
        return

    # No chat to run, but keep the server alive so the page stays reachable.
    print("  (Server staying up. Ctrl+C to quit.)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    print(" Relay stopped.")


if __name__ == "__main__":
    main()