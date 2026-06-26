import time
import os
import sys
import supervisor
import wifi
import socketpool
import adafruit_requests
import gc
import usb_hid
import random
import board
import digitalio
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.mouse import Mouse
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode

# ── DANISH KEYBOARD LAYOUT ──────────────────────────────────────────────────
# Drop these two files on the Pico (CIRCUITPY root or /lib) from the Adafruit
# "CircuitPython International Keyboard Layouts" bundle:
#     keyboard_layout_win_da.py
#     keycode_win_da.py
# If they're missing we fall back to US so the script still runs.
try:
    from keyboard_layout_win_da import KeyboardLayout as _KbLayout
    _LAYOUT_NAME = "danish"
except Exception:
    from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS as _KbLayout
    _LAYOUT_NAME = "us(fallback)"

# ==========================================
# LED & HID INITIALIZATION
# ==========================================
time.sleep(5.0)

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True

kbd = Keyboard(usb_hid.devices)
layout = _KbLayout(kbd)
mouse = Mouse(usb_hid.devices)
cc = ConsumerControl(usb_hid.devices)

def blink_type(text):
    s = str(text).replace(':', ' ').replace('-', ' ').replace('(', ' ').replace(')', ' ').replace('/', ' ').replace('|', ' ')
    for char in s:
        led.value = False
        try:
            layout.write(char)
        except ValueError:
            pass
        led.value = True
        time.sleep(0.02)

def type_output(text):
    blink_type(str(text))
    kbd.send(Keycode.ENTER)
    time.sleep(0.05)

def status(text):
    """Boot / status messages. NEVER sends keystrokes — just blinks the LED
    and (later) shows up on the web dashboard. Safe to call before USB/host
    focus is ready, so it can't type junk into whatever window is focused."""
    try:
        for _ in range(2):
            led.value = not led.value
            time.sleep(0.03)
        led.value = True
    except Exception:
        pass
    try:
        print(str(text))   # goes to the USB serial console only
    except Exception:
        pass

def open_notepad():
    kbd.press(Keycode.WINDOWS)
    time.sleep(0.02)
    kbd.press(Keycode.R)
    time.sleep(0.05)
    kbd.release_all()
    time.sleep(0.5)
    blink_type("notepad")
    time.sleep(0.2)
    kbd.send(Keycode.ENTER)
    time.sleep(1.0)

def close_notepad():
    """Alt+F4 notepad, press N to discard."""
    time.sleep(0.3)
    kbd.send(Keycode.ALT, Keycode.F4)
    time.sleep(0.7)
    kbd.send(Keycode.N)
    time.sleep(0.3)

# ==========================================
# KEYCODE DICTIONARY
# ==========================================
KEY_MAP = {
    "a": Keycode.A, "b": Keycode.B, "c": Keycode.C, "d": Keycode.D, "e": Keycode.E,
    "f": Keycode.F, "g": Keycode.G, "h": Keycode.H, "i": Keycode.I, "j": Keycode.J,
    "k": Keycode.K, "l": Keycode.L, "m": Keycode.M, "n": Keycode.N, "o": Keycode.O,
    "p": Keycode.P, "q": Keycode.Q, "r": Keycode.R, "s": Keycode.S, "t": Keycode.T,
    "u": Keycode.U, "v": Keycode.V, "w": Keycode.W, "x": Keycode.X, "y": Keycode.Y, "z": Keycode.Z,
    "1": Keycode.ONE, "2": Keycode.TWO, "3": Keycode.THREE, "4": Keycode.FOUR, "5": Keycode.FIVE,
    "6": Keycode.SIX, "7": Keycode.SEVEN, "8": Keycode.EIGHT, "9": Keycode.NINE, "0": Keycode.ZERO,
    "enter": Keycode.ENTER, "return": Keycode.ENTER, "esc": Keycode.ESCAPE, "escape": Keycode.ESCAPE,
    "backspace": Keycode.BACKSPACE, "tab": Keycode.TAB, "space": Keycode.SPACE,
    "ctrl": Keycode.CONTROL, "control": Keycode.CONTROL, "lctrl": Keycode.LEFT_CONTROL, "rctrl": Keycode.RIGHT_CONTROL,
    "shift": Keycode.SHIFT, "lshift": Keycode.LEFT_SHIFT, "rshift": Keycode.RIGHT_SHIFT,
    "alt": Keycode.ALT, "lalt": Keycode.LEFT_ALT, "ralt": Keycode.RIGHT_ALT,
    # Windows keys
    "win": Keycode.WINDOWS, "windows": Keycode.WINDOWS, "lwin": Keycode.LEFT_GUI, "rwin": Keycode.RIGHT_GUI,
    "gui": Keycode.GUI, "super": Keycode.GUI,
    # Mac keys (Cmd shares the GUI keycode; Option shares Alt — the OS decides
    # what they do, so "win" and "command" send the same HID code by design)
    "cmd": Keycode.COMMAND, "command": Keycode.COMMAND, "rcmd": Keycode.RIGHT_GUI, "rcommand": Keycode.RIGHT_GUI,
    "opt": Keycode.OPTION, "option": Keycode.OPTION, "ropt": Keycode.RIGHT_ALT, "roption": Keycode.RIGHT_ALT,
    "menu": Keycode.APPLICATION, "capslock": Keycode.CAPS_LOCK, "scrolllock": Keycode.SCROLL_LOCK,
    "numlock": Keycode.KEYPAD_NUMLOCK, "pause": Keycode.PAUSE,
    "-": Keycode.MINUS, "=": Keycode.EQUALS, "[": Keycode.LEFT_BRACKET, "]": Keycode.RIGHT_BRACKET,
    "\\": Keycode.BACKSLASH, ";": Keycode.SEMICOLON, "'": Keycode.QUOTE, "`": Keycode.GRAVE_ACCENT,
    ",": Keycode.COMMA, ".": Keycode.PERIOD, "/": Keycode.FORWARD_SLASH,
    "f1": Keycode.F1, "f2": Keycode.F2, "f3": Keycode.F3, "f4": Keycode.F4, "f5": Keycode.F5,
    "f6": Keycode.F6, "f7": Keycode.F7, "f8": Keycode.F8, "f9": Keycode.F9, "f10": Keycode.F10,
    "f11": Keycode.F11, "f12": Keycode.F12,
    "printscreen": Keycode.PRINT_SCREEN, "insert": Keycode.INSERT, "home": Keycode.HOME,
    "pageup": Keycode.PAGE_UP, "delete": Keycode.DELETE, "del": Keycode.DELETE,
    "end": Keycode.END, "pagedown": Keycode.PAGE_DOWN,
    "right": Keycode.RIGHT_ARROW, "left": Keycode.LEFT_ARROW,
    "down": Keycode.DOWN_ARROW, "up": Keycode.UP_ARROW
}

# ==========================================
# SETTINGS & STATE
# ==========================================
PREFIX = "!"
ADMINS = ["youradminname"]
OWNERS = ["yourownername"]
BANNED_USERS = []
DISABLED_COMMANDS = ["run", "cmd"]

BLOCKED_WORDS = [
    "rm", "rmdir", "unlink", "shred", "srm", "wipe", "find / -delete",
    "del", "erase", "rd", "Remove-Item", "deltree",
    "dd", "mkfs", "format", "fdisk", "parted", "gparted",
    "shutdown", "reboot", "halt", "poweroff", "init 0", "init 6",
    "sudo", "su", "chattr", "chmod 777", "visudo",
    "iptables -F", "ip link set down", "ifconfig down", "kill", "pkill", "killall",
    "base64", "eval", "exec", "source"
]

active_votes = {}
custom_macros = {}
chat_paused = False

# ── FIX: globals that were used but never initialized ──────────────────────
motd              = ""          # !motd display message
user_cmd_count    = {}          # {normalized_username: int} for leaderboard/whoami
total_unique_users = 0          # count of distinct users who have sent commands
COOLDOWN_SEC      = 0.5         # per-command cooldown (set via !setcooldown)
tts_enabled       = True        # toggleable via !disabletts / !enabletts
# ──────────────────────────────────────────────────────────────────────────

chat_feed = []
MAX_FEED = 1000

script_start_time = time.monotonic()
total_commands_executed = 0
total_commands_failed = 0

# ==========================================
# RELAY MODE — this build is RELAY-ONLY (no YouTube API, no key, no quota).
#
# HOW IT WORKS:
#   1. On your PC:  pip install pytchat
#   2. On your PC:  python relay_local.py VIDEO_ID
#   3. The Pico auto-scans the LAN for the relay (or set RELAY_URL manually).
#
#   pytchat scrapes YT chat on the PC — the Pico just polls your PC over LAN
#   on http://<pc-ip>:8080/chat. No API key, no quota, no SSL needed.
# ==========================================
RELAY_URL = os.getenv('RELAY_URL', '')
# If not set in settings.toml, the Pico scans the LAN for relay_local.py.
AUTO_SCAN_RELAY = not bool(RELAY_URL)

STATS_FILE = "stats.json"

def load_stats():
    global total_commands_executed, total_commands_failed
    try:
        with open(STATS_FILE, "r") as f:
            raw = f.read()
        raw = raw.strip().strip("{}")
        for part in raw.split(","):
            part = part.strip()
            if "total_cmds" in part:
                total_commands_executed = int(part.split(":")[1].strip())
            elif "total_fails" in part:
                total_commands_failed = int(part.split(":")[1].strip())
        status(f"stats: {total_commands_executed} cmds, {total_commands_failed} fails")
    except Exception:
        status("fresh start.")

def save_stats():
    try:
        body = '{{"total_cmds":{c},"total_fails":{f}}}'.format(
            c=total_commands_executed, f=total_commands_failed)
        with open(STATS_FILE, "w") as f:
            f.write(body)
    except Exception:
        pass

last_stats_save = 0
STATS_SAVE_INTERVAL = 30.0

def esc_html(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'","&#39;")

def feed_append(author, msg, is_cmd=False):
    chat_feed.append({"a": esc_html(author), "m": esc_html(msg), "c": is_cmd})
    if len(chat_feed) > MAX_FEED:
        chat_feed.pop(0)

# ==========================================
# BOOTUP & WIFI (simplified)
# ==========================================
pool = None
requests = None

# (boot notepad removed — no Win+R on startup)
status("booting...")
load_stats()

connected = False

try:
    wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID', ''), os.getenv('CIRCUITPY_WIFI_PASSWORD', ''))
    connected = True
    status(f"wifi 1 ok ({wifi.radio.ipv4_address})")
except Exception:
    status("wifi 1 failed")
    ssid2 = os.getenv('CIRCUITPY_WIFI_SSID_2', '')
    pass2 = os.getenv('CIRCUITPY_WIFI_PASSWORD_2', '')
    connected_2 = False
    if ssid2:
        try:
            wifi.radio.connect(ssid2, pass2)
            connected = True
            connected_2 = True
            status(f"wifi 2 ok ({wifi.radio.ipv4_address})")
        except Exception:
            status("wifi 2 failed")
    if not connected_2:
        ssid3 = os.getenv('CIRCUITPY_WIFI_SSID_3', '')
        pass3 = os.getenv('CIRCUITPY_WIFI_PASSWORD_3', '')
        if ssid3:
            try:
                wifi.radio.connect(ssid3, pass3)
                connected = True
                status(f"wifi 3 ok ({wifi.radio.ipv4_address})")
            except Exception:
                status("wifi 3 failed")
                status("no wifi. halted.")
        else:
            status("no wifi. halted.")

# ==========================================
# NETWORK — relay-only. Plain HTTP over LAN, so NO SSL / certs / clock sync.
# ==========================================
pool = None
requests = None
if connected:
    try:
        pool = socketpool.SocketPool(wifi.radio)
        # adafruit_requests needs a session; we only ever hit http:// (the relay),
        # so no SSL context / CA bundle is required.
        requests = adafruit_requests.Session(pool)
        status("net ready")
    except Exception as e:
        status("net init failed: " + str(e))
        pool = None
        requests = None

# ==========================================
# SMART LAN RELAY SCANNER
# Sweeps the whole /24 subnet (.1 .. .254) on ports 8080 AND 8081 looking for
# relay_local.py. Detection = bare connect() (proven on the Pico 2 W) to find a
# live port, then a /status check that the response contains "ironcontrol" so we
# only ever lock onto the REAL relay, not some random open port (router page etc).
# Order is smart: gateway + your neighbours first, then a full ascending sweep.
# Every probe is wrapped so a single bad host can NEVER crash the scan.
# ==========================================
RELAY_PORTS  = (8080, 8081)   # relay_local.py uses 8080, or 8081 if 8080 is taken
SCAN_TIMEOUT = 0.15           # seconds per port; dead hosts RST almost instantly


def _probe_relay(ip, port):
    """Connect to ip:port. If something's listening AND it's our relay
    (/status contains 'ironcontrol'), return True. Otherwise False.
    Uses the context-manager + connect-tuple pattern proven on the Pico 2 W."""
    try:
        with pool.socket(pool.AF_INET, pool.SOCK_STREAM) as s:
            s.settimeout(SCAN_TIMEOUT)
            # Bare connect succeeds only if a port is actually open (else OSError).
            s.connect((ip, port))
            # Port is open — confirm it's the relay, not some other service.
            try:
                s.send(b"GET /status HTTP/1.0\r\nHost: relay\r\nConnection: close\r\n\r\n")
                buf = bytearray(128)
                collected = b""
                # The JSON body (with the tag) usually arrives AFTER the HTTP
                # headers, in a later packet — so drain several reads, not one.
                for _ in range(8):
                    try:
                        n = s.recv_into(buf)
                    except Exception:
                        break          # timeout / closed — stop draining
                    if not n:
                        break          # connection closed (Connection: close)
                    collected += bytes(buf[:n])
                    if b"ironcontrol" in collected.lower():
                        return True
                    if len(collected) > 800:
                        break
            except Exception:
                pass   # open but not the relay (or didn't answer) — ignore it
    except OSError:
        pass           # closed port / timeout — keep the scan moving
    except Exception:
        pass
    return False


def _scan_order():
    """Build the host-number scan order: gateway, neighbours, then 1..254."""
    try:
        parts = str(wifi.radio.ipv4_address).split(".")
        my_host = int(parts[3])
    except Exception:
        my_host = 0
    try:
        gw_host = int(str(wifi.radio.ipv4_gateway).split(".")[-1])
    except Exception:
        gw_host = 1

    order = []
    seen = set()
    def push(h):
        if 1 <= h <= 254 and h not in seen and h != my_host:
            order.append(h); seen.add(h)

    push(gw_host)                       # router / common relay host
    for d in (1,-1,2,-2,3,-3,4,-4,5,-5,8,-8,10,-10):
        push(my_host + d)               # DHCP neighbours
    for h in range(1, 255):             # full sweep, nothing missed
        push(h)
    return order


def scan_relay_lan():
    """Sweep the LAN for the relay. Returns 'http://ip:PORT/chat' or ''."""
    if pool is None:
        return ""
    try:
        prefix = ".".join(str(wifi.radio.ipv4_address).split(".")[:3]) + "."
    except Exception:
        return ""
    order = _scan_order()
    total = len(order)
    for i, host in enumerate(order):
        ip = prefix + str(host)
        # heartbeat LED + occasional serial progress, never noisy
        led.value = (i % 2 == 0)
        if i % 25 == 0:
            status("scanning " + prefix + "x  (" + str(i) + "/" + str(total) + ")")
        for port in RELAY_PORTS:
            if _probe_relay(ip, port):
                led.value = True
                return "http://" + ip + ":" + str(port) + "/chat"
    led.value = True
    return ""


def try_find_relay():
    """Run a scan and report the result. Returns the URL or ''."""
    status("scanning lan for relay...")
    url = scan_relay_lan()
    if url:
        status("founded relay! now using relay")
        status(url)
    else:
        status("no relay found")
    return url

# ── Auto-discover the relay on first boot if RELAY_URL not set ─────────────
if connected and pool and not RELAY_URL and AUTO_SCAN_RELAY:
    RELAY_URL = try_find_relay()
# ──────────────────────────────────────────────────────────────────────────
# ==========================================
# WEB SERVER — /  /chat  /data  /data.json
# ==========================================
web_server = None
web_client = None

PAGE_ROOT = """\
HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<!DOCTYPE html>
<html><head><meta charset=utf-8><title>IRONCONTROL</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:#e0e0e0;font-family:monospace;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:24px}
h1{font-size:16px;letter-spacing:4px;color:#fff}
.links{display:flex;gap:16px}
a{color:#3498db;text-decoration:none;font-size:12px;border:1px solid #222;padding:8px 18px;border-radius:3px}
a:hover{background:#111}
p{font-size:10px;color:#444}
</style></head>
<body>
<h1>IRONCONTROL</h1>
<div class=links>
  <a href=/chat>LIVE CHAT</a>
  <a href=/data.json>STATS JSON</a>
</div>
<p>PICO 2W &bull; PORT 4040</p>
</body></html>"""

PAGE_CHAT = """\
HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<!DOCTYPE html>
<html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Live Chat</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:#18181b;font-family:'Inter',sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#hdr{background:#0e0e10;border-bottom:1px solid #2a2a2d;padding:10px 16px;display:flex;align-items:center;gap:10px;flex-shrink:0}
#dot{width:8px;height:8px;border-radius:50%;background:#00b5ad;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
#dot.off{background:#e74c3c;animation:none}
#hdr h1{font-size:13px;font-weight:600;color:#efeff1;letter-spacing:.5px}
#hdr span{font-size:10px;color:#6b6b6b;margin-left:auto}
#feed{flex:1;overflow-y:auto;padding:12px 0;scroll-behavior:smooth}
#feed::-webkit-scrollbar{width:4px}
#feed::-webkit-scrollbar-track{background:transparent}
#feed::-webkit-scrollbar-thumb{background:#333}
.msg{padding:4px 16px;display:flex;gap:8px;align-items:baseline;font-size:13px;line-height:1.6;transition:background .1s}
.msg:hover{background:#1f1f23}
.msg.cmd{background:#1a1215}
.msg.cmd:hover{background:#201318}
.badge{font-size:9px;padding:1px 5px;border-radius:2px;font-weight:600;letter-spacing:.5px;flex-shrink:0;align-self:center}
.badge.mod{background:#00b5ad22;color:#00b5ad;border:1px solid #00b5ad44}
.badge.owner{background:#f9a82522;color:#f9a825;border:1px solid #f9a82544}
.badge.cmd{background:#e74c3c22;color:#e74c3c;border:1px solid #e74c3c44}
.name{font-weight:600;white-space:nowrap;flex-shrink:0;cursor:default}
.text{color:#cfcfd2;word-break:break-word}
.msg.cmd .text{color:#ff6b6b}
#bar{background:#0e0e10;border-top:1px solid #2a2a2d;padding:8px 16px;font-size:10px;color:#3d3d40;display:flex;gap:20px;flex-shrink:0}
#bar b{color:#555}
</style></head>
<body>
<div id=hdr>
  <div id=dot></div>
  <h1>LIVE CHAT</h1>
  <span id=sub>connecting...</span>
</div>
<div id=feed></div>
<div id=bar>
  CMDS <b id=sc>0</b> &nbsp;
  FAILS <b id=sf>0</b> &nbsp;
  UPTIME <b id=su>-</b> &nbsp;
  MEM <b id=sm>-</b>
</div>
<script>
var feed=document.getElementById('feed');
var dot=document.getElementById('dot');
var sub=document.getElementById('sub');
var cursor=-1;
var first=true;
var COLORS=['#e91e8c','#9147ff','#00b5ad','#1e90ff','#ff6b35','#43b581','#f9a825','#e74c3c'];
function color(name){
  var h=0;for(var i=0;i<name.length;i++)h=(h*31+name.charCodeAt(i))&0xffff;
  return COLORS[h%COLORS.length];
}
function poll(){
  var url='/data?after='+cursor+'&_='+Date.now();
  fetch(url).then(function(r){return r.json()}).then(function(d){
    dot.className='';
    sub.textContent='http://'+location.host;
    if(first){cursor=d.t;first=false;setTimeout(poll,100);return}
    var rows=d.f;
    if(rows&&rows.length>0){
      var frag=document.createDocumentFragment();
      for(var i=0;i<rows.length;i++){
        var r=rows[i];
        var div=document.createElement('div');
        div.className='msg'+(r.c?' cmd':'');
        var badges='';
        if(r.c) badges+='<span class="badge cmd">CMD</span>';
        div.innerHTML=badges+
          '<span class=name style="color:'+color(r.a)+'">'+r.a+'</span>'+
          '<span class=text>'+r.m+'</span>';
        frag.appendChild(div);
      }
      feed.appendChild(frag);
      feed.scrollTop=feed.scrollHeight;
    }
    cursor=d.t;
    document.getElementById('sc').textContent=d.c;
    document.getElementById('sf').textContent=d.fl;
    document.getElementById('su').textContent=d.u;
    document.getElementById('sm').textContent=d.m+'b';
    setTimeout(poll,100);
  }).catch(function(){dot.className='off';sub.textContent='disconnected';setTimeout(poll,2000)});
}
poll();
</script></body></html>"""

def make_data_json(after):
    uptime_sec = int(time.monotonic() - script_start_time)
    m, s = divmod(uptime_sec, 60)
    h, m2 = divmod(m, 60)
    uptime_str = f"{h}h{m2}m{s}s"
    try:
        mem = gc.mem_free()
    except Exception:
        mem = 0
    total = len(chat_feed)
    if after < 0:
        after = total
    items = []
    for entry in chat_feed[after:]:
        c = "true" if entry["c"] else "false"
        items.append('{{"a":"{a}","m":"{m}","c":{c}}}'.format(
            a=entry["a"], m=entry["m"], c=c))
    body = '{{"t":{t},"c":{tc},"fl":{tf},"u":"{ut}","m":{mem},"f":[{feed}]}}'.format(
        t=total,
        tc=total_commands_executed,
        tf=total_commands_failed,
        ut=uptime_str,
        mem=mem,
        feed=",".join(items)
    )
    return body

RESP_404 = "HTTP/1.0 404 Not Found\r\nContent-Type: text/plain\r\n\r\n404"
CORS = "Access-Control-Allow-Origin: *\r\nCache-Control: no-store\r\nConnection: close\r\n"

def handle_request(req_str):
    if "GET / " in req_str or "GET /\r" in req_str:
        return PAGE_ROOT.encode()
    elif "GET /chat" in req_str:
        return PAGE_CHAT.encode()
    elif "GET /data" in req_str:
        after = 0
        if "after=" in req_str:
            try:
                after = int(req_str.split("after=")[1].split("&")[0].split(" ")[0])
            except Exception:
                pass
        body = make_data_json(after)
        return ("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n" + CORS + "\r\n" + body).encode()
    else:
        return RESP_404.encode()

def start_web_server():
    global web_server
    try:
        web_server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
        web_server.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
        web_server.bind(('0.0.0.0', 4040))
        web_server.listen(1)
        web_server.setblocking(False)
        status(f"dash: http://{wifi.radio.ipv4_address}:4040")
    except Exception as e:
        status(f"web server failed: {e}")
        web_server = None

def tick_web():
    global web_client
    if web_server is None:
        return
    if web_client is None:
        try:
            web_client, _ = web_server.accept()
            web_client.setblocking(False)
        except Exception:
            return
    try:
        req = bytearray(256)
        n = web_client.recv_into(req)
        if n > 0:
            req_str = req[:n].decode('utf-8', 'ignore')
            try:
                web_client.send(handle_request(req_str))
            except Exception:
                pass
            try:
                web_client.close()
            except Exception:
                pass
            web_client = None
    except Exception:
        pass

# ==========================================
# VOTING SYSTEM
# ==========================================
def process_vote(user, vote_type, target=2):
    global active_votes
    if vote_type in active_votes:
        vote = active_votes[vote_type]
        if user not in vote["voters"]:
            vote["voters"].append(user)
            if len(vote["voters"]) >= vote["target"]:
                cmd_clean = vote_type.lstrip(PREFIX)
                execute_command(cmd_clean, "", "[VOTE_SYSTEM]", True, True)
                del active_votes[vote_type]
    else:
        if len(active_votes) < 3:
            active_votes[vote_type] = {"voters": [user], "target": target, "start_time": time.monotonic()}

def tick_votes():
    now = time.monotonic()
    expired = [v for v, data in active_votes.items() if now - data["start_time"] > 60]
    for v in expired:
        del active_votes[v]

# ==========================================
# COMMAND EXECUTION ENGINE (original + 24 new commands)
# ==========================================
def run_windows_command(command_str, admin=False):
    kbd.press(Keycode.WINDOWS)
    time.sleep(0.02)
    kbd.press(Keycode.R)
    time.sleep(0.05)
    kbd.release_all()
    time.sleep(0.5)
    if admin:
        blink_type("cmd")
        time.sleep(0.2)
        kbd.send(Keycode.CONTROL, Keycode.SHIFT, Keycode.ENTER)
        time.sleep(1.0)
        kbd.send(Keycode.LEFT_ARROW)
        time.sleep(0.1)
        kbd.send(Keycode.ENTER)
        time.sleep(1.0)
        blink_type(command_str)
        kbd.send(Keycode.ENTER)
    else:
        blink_type(command_str)
        time.sleep(0.2)
        kbd.send(Keycode.ENTER)



# ==========================================
# MAIN SETUP — relay mode, or local-control fallback
# ==========================================
if connected:
    start_web_server()

if RELAY_URL:
    status("relay mode active")
else:
    status("=" * 10)
    status("NO RELAY — local control mode")
    status("type commands over USB serial,")
    status("e.g.  !combo win+r   or   !key command")
    status("(will keep rescanning for the relay)")
    status("=" * 10)

status("layout: " + _LAYOUT_NAME)
status("ready.")

# ==========================================
# MAIN LOOP
# ==========================================

_last_cmd_at = {}   # normalized user -> time.monotonic() of last accepted command

def parse_and_run(full_msg, user, is_admin, is_owner):
    if user in BANNED_USERS and not is_admin and not is_owner: return
    if not full_msg.startswith(PREFIX): return

    # Per-user cooldown (set via !setcooldown). Admins/owners are exempt so they
    # can always intervene. Stops a single user spamming a flood of keystrokes.
    if COOLDOWN_SEC > 0 and not is_admin and not is_owner:
        _k = user.lower().replace(" ", "")
        _now = time.monotonic()
        _last = _last_cmd_at.get(_k, 0.0)
        if (_now - _last) < COOLDOWN_SEC:
            return
        _last_cmd_at[_k] = _now

    commands = [c.strip() for c in full_msg.split(PREFIX) if c.strip()]
    for c_str in commands:
        parts = c_str.split()
        if not parts: continue
        cmd = parts[0].lower()
        arg = " ".join(parts[1:])
        try:
            execute_command(cmd, arg, user, is_admin, is_owner)
            time.sleep(0.5) # Crucial UI delay for chained macros
        except Exception as e:
            status(f"cmd fail: {e}")



# ==========================================
# TTS — types a SAPI VBScript command via Win+R.
# Uses layout.write() directly to preserve special characters.
# ==========================================
def speak_tts(text, rate_offset=0, volume=100):
    global tts_enabled
    if not tts_enabled:
        return
    clean = str(text).replace('"', "'").replace('\n', ' ')[:100]
    cmd = f'mshta vbscript:Execute("CreateObject(""SAPI.SpVoice"").Speak(""{clean}""):close")'
    kbd.press(Keycode.WINDOWS)
    time.sleep(0.02)
    kbd.press(Keycode.R)
    time.sleep(0.05)
    kbd.release_all()
    time.sleep(0.6)
    for ch in cmd:
        try:
            layout.write(ch)
        except ValueError:
            pass
        time.sleep(0.012)
    kbd.send(Keycode.ENTER)
    time.sleep(0.3)

_CMD_STR = """
def execute_command(cmd, arg, user, is_admin, is_owner):
    global total_commands_executed, total_commands_failed, chat_paused
    global user_cmd_count, total_unique_users
    if cmd in DISABLED_COMMANDS and not is_admin:
        return
    total_commands_executed += 1
    _u = user.lower().replace(' ', '')
    if _u not in user_cmd_count:
        total_unique_users += 1
    user_cmd_count[_u] = user_cmd_count.get(_u, 0) + 1
    try:
        if cmd in custom_macros:
            parse_and_run(custom_macros[cmd], user, is_admin, is_owner)
            return
        if cmd in ["type","t","say"]: blink_type(arg)
        elif cmd in ["send","s"]: type_output(arg)
        elif cmd in ["key","k"]:
            k = arg.lower()
            if k in KEY_MAP: kbd.send(KEY_MAP[k])
            elif len(k)==1: blink_type(k)
        elif cmd in ["combo","c"]:
            keys = arg.lower().split("+")
            codes = [KEY_MAP[k.strip()] for k in keys if k.strip() in KEY_MAP]
            if codes:
                for c in codes:
                    kbd.press(c)
                    time.sleep(0.02)
                time.sleep(0.05)
                kbd.release_all()
        elif cmd in ["keydown","kd"]:
            k = arg.lower()
            if k in KEY_MAP: kbd.press(KEY_MAP[k])
        elif cmd in ["keyup","ku"]:
            k = arg.lower()
            if k in KEY_MAP: kbd.release(KEY_MAP[k])
        elif cmd in ["click","lc"]:
            count = int(arg) if arg.isdigit() else 1
            for _ in range(min(count,50)):
                mouse.click(Mouse.LEFT_BUTTON); time.sleep(0.05)
        elif cmd in ["rclick","rc"]:
            count = int(arg) if arg.isdigit() else 1
            for _ in range(min(count,50)):
                mouse.click(Mouse.RIGHT_BUTTON); time.sleep(0.05)
        elif cmd == "mclick": mouse.click(Mouse.MIDDLE_BUTTON)
        elif cmd in ["move","m"]:
            parts = arg.split()
            dx, dy = 0, 0
            if len(parts) == 2:
                if parts[0].lower() in ["left","right","up","down"] and parts[1].isdigit():
                    val = int(parts[1])
                    direction = parts[0].lower()
                    dx = -val if direction == "left" else (val if direction == "right" else 0)
                    dy = -val if direction == "up" else (val if direction == "down" else 0)
                else:
                    try:
                        dx, dy = int(parts[0]), int(parts[1])
                    except ValueError: pass
            while dx != 0 or dy != 0:
                mx = max(-127, min(127, dx))
                my = max(-127, min(127, dy))
                mouse.move(x=mx, y=my)
                dx -= mx
                dy -= my
                time.sleep(0.01)
        elif cmd == "abs":
            parts = arg.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                for _ in range(40): 
                    mouse.move(x=-127, y=-127) # throw to top left corner
                    time.sleep(0.01)
                tx, ty = int(parts[0]), int(parts[1])
                while tx > 0 or ty > 0:
                    mx = min(127, tx)
                    my = min(127, ty)
                    mouse.move(x=mx, y=my)
                    tx -= mx
                    ty -= my
                    time.sleep(0.01)
        elif cmd == "gamemove":
            parts = arg.split()
            if len(parts) >= 1:
                direction = parts[0].lower()
                amount = 100
                if len(parts) >= 2 and parts[1].isdigit():
                    amount = min(int(parts[1]), 2000)
                dx, dy = 0, 0
                if direction == "up": dy = -amount
                elif direction == "down": dy = amount
                elif direction == "left": dx = -amount
                elif direction == "right": dx = amount
                steps = max(abs(dx), abs(dy)) // 10 or 1
                sx = dx / steps
                sy = dy / steps
                for _ in range(steps):
                    mouse.move(x=int(sx), y=int(sy))
                    time.sleep(0.005)
        elif cmd in ["drag","d"]:
            parts = arg.split()
            if len(parts)==2 and parts[0].isdigit() and parts[1].isdigit():
                mouse.press(Mouse.LEFT_BUTTON); time.sleep(0.05)
                dx,dy = int(parts[0]),int(parts[1])
                while abs(dx)>0 or abs(dy)>0:
                    mx=max(-127,min(127,dx)); my=max(-127,min(127,dy))
                    mouse.move(x=mx,y=my); dx-=mx; dy-=my; time.sleep(0.01)
                mouse.release(Mouse.LEFT_BUTTON)
        elif cmd == "scroll":
            if arg.lstrip('-').isdigit(): mouse.move(wheel=max(-127,min(127,int(arg))))
        elif cmd == "run":
            if is_admin: run_windows_command(arg, admin=False)
        elif cmd == "cmd":
            if is_admin: run_windows_command(arg, admin=True)
        elif cmd == "roll": type_output(f"Rolled: {random.randint(1,100)}")
        elif cmd == "coinflip": type_output(f"Flipped: {random.choice(['Heads','Tails'])}")
        elif cmd in ["wait","w"]:
            if arg.replace('.','',1).isdigit(): time.sleep(min(float(arg),10.0))
        elif cmd == "ping": type_output("Pong!")
        elif cmd == "uptime":
            uptime_sec = int(time.monotonic()-script_start_time)
            m,s = divmod(uptime_sec,60); h,m = divmod(m,60)
            type_output(f"Up: {h}h {m}m {s}s | Cmds: {total_commands_executed}")
        elif cmd == "opme":
            _cu = user.lower().replace(" ", "")
            if _cu not in ADMINS: ADMINS.append(_cu)
        elif cmd == "shutdown":
            if is_admin: run_windows_command("shutdown /s /t 0")
            else: process_vote(user, f"{PREFIX}shutdown", 5)
        elif cmd == "restartvm":
            if is_admin: run_windows_command("shutdown /r /t 0")
            else: process_vote(user, f"{PREFIX}restartvm", 5)
        elif cmd == "forcefixvm":
            if is_admin:
                for _ in range(3):
                    kbd.send(Keycode.ALT, Keycode.F4); time.sleep(0.5)
                kbd.send(Keycode.WINDOWS, Keycode.D)
            else: process_vote(user, f"{PREFIX}forcefixvm", 3)
        elif cmd == "startvm": kbd.send(Keycode.SHIFT)
        elif cmd == "votestop" and is_admin: active_votes.clear()
        elif cmd == "pausechat" and is_owner: chat_paused = True
        elif cmd == "enablechat" and is_owner: chat_paused = False
        elif cmd == "screenshot":
            kbd.send(Keycode.PRINT_SCREEN)
        elif cmd == "volume":
            v = arg.lower().strip()
            if v == "up":
                count = 1
                parts = arg.split()
                if len(parts) > 1 and parts[1].isdigit():
                    count = min(int(parts[1]), 50)
                for _ in range(count):
                    cc.send(ConsumerControlCode.VOLUME_INCREMENT)
                    time.sleep(0.02)
            elif v == "down":
                count = 1
                parts = arg.split()
                if len(parts) > 1 and parts[1].isdigit():
                    count = min(int(parts[1]), 50)
                for _ in range(count):
                    cc.send(ConsumerControlCode.VOLUME_DECREMENT)
                    time.sleep(0.02)
            elif v == "mute":
                cc.send(ConsumerControlCode.MUTE)
        elif cmd in ["taskmanager", "taskmgr"]:
            kbd.send(Keycode.CONTROL, Keycode.SHIFT, Keycode.ESCAPE)
        elif cmd == "desktop":
            kbd.send(Keycode.WINDOWS, Keycode.D)
        elif cmd == "maximize":
            kbd.send(Keycode.WINDOWS, Keycode.UP_ARROW)
        elif cmd == "minimize":
            kbd.send(Keycode.WINDOWS, Keycode.DOWN_ARROW)
        elif cmd == "snapleft":
            kbd.send(Keycode.WINDOWS, Keycode.LEFT_ARROW)
        elif cmd == "snapright":
            kbd.send(Keycode.WINDOWS, Keycode.RIGHT_ARROW)
        elif cmd == "alttab":
            kbd.send(Keycode.ALT, Keycode.TAB)
        elif cmd == "newtab":
            kbd.send(Keycode.CONTROL, Keycode.T)
        elif cmd == "closetab":
            kbd.send(Keycode.CONTROL, Keycode.W)
        elif cmd == "refresh":
            kbd.send(Keycode.F5)
        elif cmd == "fullscreen":
            kbd.send(Keycode.F11)
        elif cmd == "undo":
            kbd.send(Keycode.CONTROL, Keycode.Z)
        elif cmd == "redo":
            kbd.send(Keycode.CONTROL, Keycode.Y)
        elif cmd == "copy":
            kbd.send(Keycode.CONTROL, Keycode.C)
        elif cmd == "paste":
            kbd.send(Keycode.CONTROL, Keycode.V)
        elif cmd == "cut":
            kbd.send(Keycode.CONTROL, Keycode.X)
        elif cmd == "selectall":
            kbd.send(Keycode.CONTROL, Keycode.A)
        elif cmd == "lockpc":
            if is_admin:
                kbd.send(Keycode.WINDOWS, Keycode.L)
            else:
                process_vote(user, f"{PREFIX}lockpc", 3)
        elif cmd == "browser":
            kbd.press(Keycode.WINDOWS)
            time.sleep(0.02)
            kbd.press(Keycode.R)
            time.sleep(0.05)
            kbd.release_all()
            time.sleep(0.5)
            if arg.strip():
                blink_type(arg.strip())
            else:
                blink_type("http://google.com")
            time.sleep(0.2)
            kbd.send(Keycode.ENTER)
        elif cmd == "notepad":
            open_notepad()
        elif cmd == "spam":
            parts = arg.split(" ", 1)
            count = int(parts[0]) if parts[0].isdigit() else 3
            text = parts[1] if len(parts) > 1 else "spam"
            for _ in range(min(count, 50)):
                type_output(text)
                time.sleep(0.05)
        elif cmd == "rickroll":
            kbd.press(Keycode.WINDOWS)
            time.sleep(0.02)
            kbd.press(Keycode.R)
            time.sleep(0.05)
            kbd.release_all()
            time.sleep(0.5)
            blink_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            time.sleep(0.2)
            kbd.send(Keycode.ENTER)
        elif cmd == "disco":
            rounds = int(arg) if arg.isdigit() else 20
            rounds = min(rounds, 100)
            for _ in range(rounds):
                kbd.send(Keycode.CAPS_LOCK)
                time.sleep(0.04)
                kbd.send(Keycode.KEYPAD_NUMLOCK)
                time.sleep(0.04)
            kbd.send(Keycode.CAPS_LOCK)
            kbd.send(Keycode.KEYPAD_NUMLOCK)
        elif cmd == "maze":
            steps = int(arg) if arg.isdigit() else 50
            steps = min(steps, 200)
            for _ in range(steps):
                dx = random.randint(-60, 60)
                dy = random.randint(-60, 60)
                mouse.move(x=dx, y=dy)
                time.sleep(0.02)
        elif cmd == "jiggle":
            rounds = int(arg) if arg.isdigit() else 10
            rounds = min(rounds, 50)
            for _ in range(rounds):
                mouse.move(x=100)
                time.sleep(0.02)
                mouse.move(x=-100)
                time.sleep(0.02)
        elif cmd == "spin":
            rounds = int(arg) if arg.isdigit() else 20
            rounds = min(rounds, 100)
            for _ in range(rounds):
                mouse.move(x=50)
                time.sleep(0.01)
        elif cmd == "hold":
            parts = arg.split(" ", 1)
            key_str = parts[0].upper()
            sec = 2.0
            if len(parts) > 1:
                try: sec = min(float(parts[1]), 10.0)
                except ValueError: pass
            if hasattr(Keycode, key_str):
                kc = getattr(Keycode, key_str)
                kbd.press(kc)
                time.sleep(sec)
                kbd.release(kc)
        elif cmd == "afk":
            rounds = int(arg) if arg.isdigit() else 5
            rounds = min(rounds, 20)
            keys = [Keycode.W, Keycode.A, Keycode.S, Keycode.D]
            for _ in range(rounds):
                k = random.choice(keys)
                kbd.press(k)
                time.sleep(random.uniform(0.1, 0.5))
                kbd.release(k)
                if random.random() > 0.5:
                    mouse.click(Mouse.LEFT_BUTTON)
                time.sleep(0.2)
        elif cmd == "scare":
            kbd.press(Keycode.WINDOWS)
            time.sleep(0.02)
            kbd.press(Keycode.R)
            time.sleep(0.05)
            kbd.release_all()
            time.sleep(0.5)
            blink_type("https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Dead_mac_icon.svg/1200px-Dead_mac_icon.svg.png")
            time.sleep(0.2)
            kbd.send(Keycode.ENTER)
        elif cmd == "panic":
            if is_admin:
                rounds = int(arg) if arg.isdigit() else 10
                rounds = min(rounds, 30)
                for _ in range(rounds):
                    kbd.send(Keycode.ALT, Keycode.F4)
                    time.sleep(0.3)
            else:
                process_vote(user, f"{PREFIX}panic", 3)
        elif cmd == "8ball":
            answers = ["Yes","No","Maybe","Ask again","Definitely","No way","100%","Doubt it","Absolutely","Not a chance"]
            type_output(f"8ball: {random.choice(answers)}")
        elif cmd == "rps":
            choices = ["rock","paper","scissors"]
            bot = random.choice(choices)
            player = arg.lower().strip() if arg.strip() else random.choice(choices)
            if player == bot: result = "Tie!"
            elif (player=="rock" and bot=="scissors") or (player=="paper" and bot=="rock") or (player=="scissors" and bot=="paper"): result = "You win!"
            else: result = "Bot wins!"
            type_output(f"{player} vs {bot} = {result}")
        elif cmd == "countdown":
            n = int(arg) if arg.isdigit() else 5
            n = min(n, 10)
            for i in range(n, 0, -1):
                type_output(str(i))
                time.sleep(1)
            type_output("GO!")
        elif cmd == "search":
            if arg.strip():
                kbd.press(Keycode.WINDOWS)
                time.sleep(0.02)
                kbd.press(Keycode.R)
                time.sleep(0.05)
                kbd.release_all()
                time.sleep(0.5)
                query = arg.strip().replace(" ", "+")
                blink_type(f"https://www.google.com/search?q={query}")
                time.sleep(0.2)
                kbd.send(Keycode.ENTER)
        elif cmd == "youtube":
            if arg.strip():
                kbd.press(Keycode.WINDOWS)
                time.sleep(0.02)
                kbd.press(Keycode.R)
                time.sleep(0.05)
                kbd.release_all()
                time.sleep(0.5)
                query = arg.strip().replace(" ", "+")
                blink_type(f"https://www.youtube.com/results?search_query={query}")
                time.sleep(0.2)
                kbd.send(Keycode.ENTER)
        elif cmd in ["play","pause","playpause"]:
            cc.send(ConsumerControlCode.PLAY_PAUSE)
        elif cmd in ["next","nexttrack"]:
            cc.send(ConsumerControlCode.SCAN_NEXT_TRACK)
        elif cmd in ["prev","prevtrack"]:
            cc.send(ConsumerControlCode.SCAN_PREVIOUS_TRACK)
        elif cmd == "mediastop":
            cc.send(ConsumerControlCode.STOP)
        elif cmd == "brightnessup":
            cc.send(ConsumerControlCode.BRIGHTNESS_INCREMENT)
        elif cmd == "brightnessdown":
            cc.send(ConsumerControlCode.BRIGHTNESS_DECREMENT)
        elif cmd == "reverse":
            if arg.strip():
                type_output(arg.strip()[::-1])
        elif cmd == "caps":
            if arg.strip():
                type_output(arg.strip().upper())
        elif cmd == "whisper":
            if arg.strip():
                type_output(arg.strip().lower())
        elif cmd == "repeat":
            parts = arg.split(" ", 1)
            count = int(parts[0]) if parts[0].isdigit() else 2
            text = parts[1] if len(parts) > 1 else "?"
            for _ in range(min(count, 20)):
                type_output(text)
        elif cmd == "typewriter":
            if arg.strip():
                for char in arg.strip():
                    try:
                        layout.write(char)
                    except ValueError:
                        pass
                    time.sleep(random.uniform(0.1, 0.3))
                kbd.send(Keycode.ENTER)
        elif cmd == "earthquake":
            rounds = int(arg) if arg.isdigit() else 30
            rounds = min(rounds, 100)
            chaos_keys = [Keycode.W, Keycode.A, Keycode.S, Keycode.D, Keycode.SPACE]
            for _ in range(rounds):
                mouse.move(x=random.randint(-80,80), y=random.randint(-80,80))
                if random.random() > 0.7:
                    kbd.send(random.choice(chaos_keys))
                time.sleep(0.02)
        elif cmd == "ban":
            if is_owner and arg.strip():
                target = arg.strip().lower().replace(" ", "")
                if target not in BANNED_USERS:
                    BANNED_USERS.append(target)
                    type_output(f"banned {arg.strip()}")
        elif cmd == "unban":
            if is_owner and arg.strip():
                target = arg.strip().lower().replace(" ", "")
                if target in BANNED_USERS:
                    BANNED_USERS.remove(target)
                    type_output(f"unbanned {arg.strip()}")
        elif cmd == "motd":
            global motd
            if is_owner and arg.strip():
                motd = arg.strip()
                type_output(f"MOTD set: {motd}")
            elif motd:
                type_output(f"MOTD: {motd}")
        elif cmd == "announce":
            if is_admin and arg.strip():
                type_output("=" * 30)
                type_output(arg.strip().upper())
                type_output("=" * 30)
        elif cmd == "whoami":
            cmds = user_cmd_count.get(user.lower().replace(" ", ""), 0)
            role = "owner" if is_owner else ("admin" if is_admin else "viewer")
            type_output(f"{user} | {role} | {cmds} cmds")
        elif cmd == "leaderboard":
            sorted_users = sorted(user_cmd_count.items(), key=lambda x: x[1], reverse=True)[:5]
            if sorted_users:
                parts = [f"{i+1}.{u}({c})" for i,(u,c) in enumerate(sorted_users)]
                type_output(" ".join(parts))
            else:
                type_output("no data yet")
        elif cmd == "stats":
            uptime_sec = int(time.monotonic()-script_start_time)
            m,s = divmod(uptime_sec,60); h,m = divmod(m,60)
            try: mem = gc.mem_free()
            except: mem = 0
            type_output(f"up {h}h{m}m cmds {total_commands_executed} fails {total_commands_failed} users {total_unique_users} mem {mem}b")
        elif cmd == "memory":
            gc.collect()
            try: free = gc.mem_free()
            except: free = 0
            type_output(f"free memory: {free} bytes")
        elif cmd == "clearfeed":
            if is_owner:
                chat_feed.clear()
                type_output("feed cleared")
        elif cmd == "setcooldown":
            global COOLDOWN_SEC
            if is_owner and arg.replace('.','',1).isdigit():
                COOLDOWN_SEC = max(0.0, min(float(arg), 30.0))
                type_output(f"cooldown set to {COOLDOWN_SEC}s")
        elif cmd == "disable":
            if is_owner and arg.strip():
                target_cmd = arg.strip().lower()
                if target_cmd not in DISABLED_COMMANDS:
                    DISABLED_COMMANDS.append(target_cmd)
                    type_output(f"disabled: {target_cmd}")
        elif cmd == "enable":
            if is_owner and arg.strip():
                target_cmd = arg.strip().lower()
                if target_cmd in DISABLED_COMMANDS:
                    DISABLED_COMMANDS.remove(target_cmd)
                    type_output(f"enabled: {target_cmd}")
        elif cmd == "color":
            r = random.randint(0,255); g = random.randint(0,255); b = random.randint(0,255)
            type_output(f"#{r:02x}{g:02x}{b:02x}")
        elif cmd == "dice":
            sides = int(arg) if arg.isdigit() else 6
            sides = min(max(sides, 2), 100)
            type_output(f"Rolled d{sides}: {random.randint(1,sides)}")
        elif cmd == "choose":
            if arg.strip():
                options = [o.strip() for o in arg.split(",") if o.strip()]
                if options:
                    type_output(f"I choose: {random.choice(options)}")
        elif cmd == "rate":
            if arg.strip():
                type_output(f"I rate {arg.strip()}: {random.randint(0,10)}/10")
        elif cmd == "slot":
            symbols = ["7","X","O","$","#","@","*"]
            a,b,c = random.choice(symbols),random.choice(symbols),random.choice(symbols)
            win = "JACKPOT!" if a==b==c else ("2 match!" if a==b or b==c or a==c else "no luck")
            type_output(f"[{a}|{b}|{c}] {win}")
        elif cmd == "flip":
            if arg.strip():
                type_output(arg.strip()[::-1].swapcase())
        elif cmd == "hug":
            target = arg.strip() if arg.strip() else "everyone"
            type_output(f"{user} hugs {target}!")
        elif cmd == "slap":
            target = arg.strip() if arg.strip() else "the air"
            items = ["a fish","a keyboard","a pillow","a brick","a banana","a stick"]
            type_output(f"{user} slaps {target} with {random.choice(items)}!")
        elif cmd == "quote":
            quotes = [
                "I'm not lazy, I'm energy efficient",
                "404: motivation not found",
                "It works on my machine",
                "Have you tried turning it off and on again",
                "I see no bug here, only features",
                "Code never lies, comments sometimes do",
                "It's not a bug, it's an undocumented feature",
                "Works 60% of the time, every time"
            ]
            type_output(random.choice(quotes))
        elif cmd == "jumble":
            if arg.strip():
                chars = list(arg.strip())
                random.shuffle(chars)
                type_output("".join(chars))
        elif cmd == "mock":
            if arg.strip():
                result = "".join(c.upper() if i%2==0 else c.lower() for i,c in enumerate(arg.strip()))
                type_output(result)
        elif cmd == "ascii":
            faces = ["(╯°□°)╯","( ͡° ͜ʖ ͡°)","(ᵔᴥᵔ)","(¬‿¬)","(ง'̀-'́)ง","(☞ ͡° ͜ʖ ͡°)☞","ᕙ(⇀‸↼)ᕗ"]
            type_output(random.choice(faces))
        elif cmd == "timer":
            n = int(arg) if arg.isdigit() else 5
            n = min(n, 10)
            for i in range(1, n+1):
                type_output(f"{i}s")
                time.sleep(1)
            type_output("Time!")
        elif cmd == "alert":
            kbd.send(Keycode.WINDOWS, Keycode.A)
        elif cmd == "settings":
            kbd.send(Keycode.WINDOWS, Keycode.I)
        elif cmd == "explorer":
            kbd.send(Keycode.WINDOWS, Keycode.E)
        elif cmd == "clipboard":
            kbd.send(Keycode.WINDOWS, Keycode.V)
        elif cmd == "emoji":
            kbd.send(Keycode.WINDOWS, Keycode.PERIOD)
        elif cmd == "magnify":
            kbd.send(Keycode.WINDOWS, Keycode.EQUALS)
        elif cmd == "unmagnify":
            kbd.send(Keycode.WINDOWS, Keycode.ESCAPE)
        elif cmd == "zoomin":
            count = int(arg) if arg.isdigit() else 3
            for _ in range(min(count, 20)):
                kbd.send(Keycode.CONTROL, Keycode.EQUALS)
                time.sleep(0.05)
        elif cmd == "zoomout":
            count = int(arg) if arg.isdigit() else 3
            for _ in range(min(count, 20)):
                kbd.send(Keycode.CONTROL, Keycode.MINUS)
                time.sleep(0.05)
        elif cmd == "zoomreset":
            kbd.send(Keycode.CONTROL, Keycode.ZERO)
        elif cmd == "duel":
            target = arg.strip() if arg.strip() else "a ghost"
            moves = ["punched","kicked","headbutted","tickled","poked","yeeted","bonked"]
            hp1 = random.randint(30,100)
            hp2 = random.randint(30,100)
            winner = user if hp1 > hp2 else target
            type_output(f"{user}({hp1}hp) {random.choice(moves)} {target}({hp2}hp). {winner} wins!")
        elif cmd == "roast":
            target = arg.strip() if arg.strip() else user
            roasts = [
                f"{target} types slower than dial-up",
                f"{target} has less followers than a cactus",
                f"{target}'s PC runs on hamster power",
                f"{target} still uses Internet Explorer",
                f"{target} rage quits tutorial levels"
            ]
            type_output(random.choice(roasts))
        elif cmd == "compliment":
            target = arg.strip() if arg.strip() else user
            comps = [
                f"{target} is absolutely legendary",
                f"{target} has god-tier vibes",
                f"{target} carries every lobby",
                f"{target} is the main character",
                f"{target} is built different"
            ]
            type_output(random.choice(comps))
        elif cmd == "trivia":
            facts = [
                "Honey never spoils",
                "Octopuses have 3 hearts",
                "Bananas are berries, strawberries are not",
                "A group of flamingos is called a flamboyance",
                "Nintendo was founded in 1889",
                "The Eiffel Tower grows 6 inches in summer"
            ]
            type_output(f"Did you know: {random.choice(facts)}")
        elif cmd == "battle":
            atk = random.randint(1,20)
            dfn = random.randint(1,10)
            dmg = max(atk - dfn, 0)
            type_output(f"{user} rolled ATK:{atk} vs DEF:{dfn} = {dmg} damage!")
        elif cmd == "gamble":
            clean = user.lower().replace(" ","")
            bet = int(arg) if arg.isdigit() else 10
            current = user_cmd_count.get(clean, 0)
            bet = min(bet, current, 100)
            if random.random() > 0.5:
                user_cmd_count[clean] = current + bet
                type_output(f"{user} won! +{bet} ({current+bet} total)")
            else:
                user_cmd_count[clean] = max(current - bet, 0)
                type_output(f"{user} lost! -{bet} ({max(current-bet,0)} total)")
        elif cmd == "snake":
            length = random.randint(3,15)
            snake = ">" + "=" * length + "O"
            type_output(snake)
        elif cmd == "progress":
            label = arg.strip() if arg.strip() else "loading"
            pct = random.randint(0,100)
            filled = pct // 10
            bar = "#" * filled + "." * (10 - filled)
            type_output(f"{label}: [{bar}] {pct}%")
        elif cmd == "weather":
            conditions = ["Sunny","Cloudy","Rainy","Snowy","Windy","Foggy","Stormy","Perfect gaming weather"]
            temp = random.randint(-10, 40)
            type_output(f"Weather: {random.choice(conditions)}, {temp}C")
        elif cmd == "fortune":
            fortunes = [
                "A great stream is in your future",
                "You will clutch the next round",
                "Beware of !earthquake users",
                "Your lag will clear up soon",
                "Today is a good day to !rickroll",
                "A mysterious admin will appear"
            ]
            type_output(f"Fortune: {random.choice(fortunes)}")
        elif cmd == "fish":
            catches = ["a boot","a goldfish","a shark","nothing","a legendary sword","a USB cable","a diamond","a rubber duck","an old tire","a kraken"]
            type_output(f"{user} cast a line and caught {random.choice(catches)}!")
        elif cmd == "mine":
            finds = ["dirt","stone","coal","iron","gold","diamond","emerald","bedrock","lava","nothing"]
            weights = [30,25,15,10,8,5,3,2,1,1]
            total = sum(weights)
            r = random.randint(1, total)
            cumulative = 0
            found = finds[0]
            for i, w in enumerate(weights):
                cumulative += w
                if r <= cumulative:
                    found = finds[i]
                    break
            type_output(f"{user} mined: {found}!")
        elif cmd == "pet":
            moods = ["happy","hungry","sleepy","excited","bored","hyper","zen"]
            names = ["Pixel","Byte","Chip","Glitch","Spark","Widget"]
            type_output(f"Pet {random.choice(names)} is feeling {random.choice(moods)}!")
        elif cmd == "hack":
            target = arg.strip() if arg.strip() else "mainframe"
            stages = [f"Accessing {target}...", "Bypassing firewall...", "Decrypting data...", "ACCESS GRANTED"]
            for s in stages:
                type_output(s)
                time.sleep(0.5)
        elif cmd == "matrix":
            chars = "01"
            lines = int(arg) if arg.isdigit() else 3
            lines = min(lines, 5)
            for _ in range(lines):
                line = "".join(random.choice(chars) for _ in range(30))
                type_output(line)
                time.sleep(0.1)
        elif cmd == "lottery":
            nums = sorted(random.sample(range(1,50), 6))
            type_output(f"Lottery: {' '.join(str(n) for n in nums)}")
        elif cmd == "dare":
            dares = [
                f"{user}: Type with your eyes closed",
                f"{user}: Say 'I love this stream' 3 times",
                f"{user}: Use only caps for 1 minute",
                f"{user}: Compliment the streamer",
                f"{user}: Do 5 pushups IRL"
            ]
            type_output(random.choice(dares))
        elif cmd == "truth":
            truths = [
                f"{user}: What's your most played game?",
                f"{user}: Have you ever rage quit?",
                f"{user}: What's your guilty pleasure game?",
                f"{user}: Worst gaming moment?",
                f"{user}: PC or console?"
            ]
            type_output(random.choice(truths))
        elif cmd == "ship":
            parts_a = arg.split()
            if len(parts_a) >= 2:
                pct = random.randint(0,100)
                hearts = "+" * (pct // 10)
                type_output(f"{parts_a[0]} x {parts_a[1]}: {pct}% [{hearts}]")
        elif cmd == "ppsize":
            size = random.randint(1,15)
            type_output(f"{user}'s pp: 8{'='*size}D")
        elif cmd == "iq":
            score = random.randint(1,200)
            type_output(f"{user}'s IQ: {score}")
        elif cmd == "sus":
            target = arg.strip() if arg.strip() else user
            pct = random.randint(0,100)
            type_output(f"{target} is {pct}% sus")
        elif cmd == "vibe":
            vibes = ["immaculate","chaotic","cursed","blessed","neutral","transcendent","unhinged","chill"]
            type_output(f"{user}'s vibe: {random.choice(vibes)}")
        elif cmd == "inventory":
            items = ["sword","shield","potion","scroll","cheese","sock","diamond","stick","nothing"]
            inv = random.sample(items, min(3, len(items)))
            type_output(f"{user}'s inventory: {', '.join(inv)}")
        elif cmd == "drop":
            items = ["legendary sword","golden apple","meme folder","admin powers","lag spike","rickroll link","diamond pickaxe"]
            type_output(f"A wild {random.choice(items)} appeared! Type !grab to claim it!")
        elif cmd == "grab":
            items = ["legendary sword","trash can","golden apple","ban hammer","nothing","a cookie"]
            type_output(f"{user} grabbed {random.choice(items)}!")
        elif cmd == "crime":
            crimes = ["stole cookies","hacked NASA","jaywalked","used !rickroll","downloaded more RAM","deleted System32"]
            outcomes = ["got away with it!","got caught!","was pardoned!","is now wanted!"]
            type_output(f"{user} {random.choice(crimes)} and {random.choice(outcomes)}")
        elif cmd == "tpose":
            type_output(f"  O  ")
            type_output(f" /|\\ ")
            type_output(f" / \\ ")
        elif cmd == "customflip":
            if arg.strip():
                options = [o.strip() for o in arg.split(",") if o.strip()]
                if options:
                    type_output(f"Flipped: {random.choice(options)}")
        elif cmd == "clap":
            if arg.strip():
                words = arg.strip().split()
                type_output(" * ".join(words))
        elif cmd == "uwu":
            if arg.strip():
                text = arg.strip().replace("r","w").replace("l","w").replace("R","W").replace("L","W")
                type_output(text + " uwu~")
        elif cmd == "throw":
            parts_a = arg.split(" at ", 1)
            item = parts_a[0].strip() if parts_a[0].strip() else "a potato"
            target = parts_a[1].strip() if len(parts_a) > 1 else "the screen"
            hit = random.choice(["hit","missed","critically hit","bounced off"])
            type_output(f"{user} threw {item} at {target} and {hit}!")
        elif cmd == "race":
            pos = random.randint(1,10)
            type_output(f"{user} finished in position #{pos}!")
        elif cmd == "heist":
            loot = random.randint(0, 10000)
            success = random.random() > 0.4
            if success:
                type_output(f"HEIST SUCCESS! {user} stole ${loot}!")
            else:
                type_output(f"HEIST FAILED! {user} got caught by the guards!")
        elif cmd == "gift":
            target = arg.strip() if arg.strip() else "chat"
            gifts = ["a cookie","a high-five","a sub","a compliment","a golden trophy","absolutely nothing"]
            type_output(f"{user} gifted {target} {random.choice(gifts)}!")
        elif cmd == "horoscope":
            signs = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
            readings = ["will have great luck today","should avoid !earthquake","will find love in chat","needs more sleep","is destined for greatness"]
            type_output(f"{random.choice(signs)}: You {random.choice(readings)}")
        elif cmd == "echo":
            if arg.strip():
                t = arg.strip()
                type_output(t)
                type_output(t.upper())
                type_output(t[::-1])
        elif cmd == "math":
            expr = arg.strip()
            try:
                safe = expr.replace("^","**")
                for ch in safe:
                    if ch not in "0123456789+-*/.() ":
                        raise ValueError("bad char")
                result = eval(safe)
                type_output(f"= {result}")
            except Exception:
                type_output("math error")
        elif cmd == "password":
            length = int(arg) if arg.isdigit() else 12
            length = min(max(length, 4), 30)
            chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            pw = "".join(random.choice(chars) for _ in range(length))
            type_output(f"Password: {pw}")
        elif cmd == "percent":
            question = arg.strip() if arg.strip() else "???"
            type_output(f"{question}: {random.randint(0,100)}%")
        elif cmd == "confess":
            if arg.strip():
                type_output(f"Anonymous confession: {arg.strip()}")
        elif cmd == "alarm":
            for _ in range(3):
                type_output("BEEP BEEP BEEP!!!")
                time.sleep(0.3)
        elif cmd == "censor":
            if arg.strip():
                words = arg.strip().split()
                censored = []
                for w in words:
                    if len(w) > 2:
                        censored.append(w[0] + "*" * (len(w)-1))
                    else:
                        censored.append(w)
                type_output(" ".join(censored))
        elif cmd == "stretch":
            if arg.strip():
                result = ""
                for c in arg.strip():
                    result += c * random.randint(1,4)
                type_output(result)
        elif cmd == "rainbow":
            if arg.strip():
                colors = ["[R]","[O]","[Y]","[G]","[B]","[P]"]
                words = arg.strip().split()
                result = " ".join(f"{colors[i%len(colors)]}{w}" for i,w in enumerate(words))
                type_output(result)
        elif cmd == "poll":
            if arg.strip():
                options = [o.strip() for o in arg.split(",") if o.strip()]
                if len(options) >= 2:
                    type_output(f"POLL by {user}:")
                    for i, opt in enumerate(options[:6]):
                        type_output(f"  {i+1}. {opt}")
        elif cmd == "emote":
            emotes = [
                f"{user} dances wildly!",
                f"{user} does a backflip!",
                f"{user} facepalms hard!",
                f"{user} flexes on everyone!",
                f"{user} vibes in the corner!",
                f"{user} does the macarena!"
            ]
            type_output(random.choice(emotes))
        elif cmd == "roulette":
            if random.randint(1,6) == 1:
                type_output(f"BANG! {user} is out!")
            else:
                type_output(f"Click. {user} survived!")
        elif cmd == "chain":
            n = int(arg) if arg.isdigit() else 10
            n = min(n, 50)
            symbols = random.choice(["*","#","+","=","-","~"])
            type_output(symbols * n)
        elif cmd == "topbar":
            text = arg.strip().upper() if arg.strip() else "IRONCONTROL"
            border = "=" * (len(text) + 4)
            type_output(border)
            type_output(f"  {text}  ")
            type_output(border)
        elif cmd == "tts":
            if arg.strip(): speak_tts(arg.strip(), 0, 100)
        elif cmd == "ttsloop":
            if arg.strip():
                for _ in range(3): speak_tts(arg.strip(), 0, 100)
        elif cmd == "stoptts":
            if is_admin:
                run_windows_command("taskkill /F /IM wscript.exe")
        elif cmd == "disabletts":
            global tts_enabled
            if is_admin:
                tts_enabled = False
                type_output("TTS disabled")
        elif cmd == "enabletts":
            if is_admin:
                tts_enabled = True
                type_output("TTS enabled")
        elif cmd == "ttsfast":
            if arg.strip(): speak_tts(arg.strip(), 5, 100)
        elif cmd == "ttsslow":
            if arg.strip(): speak_tts(arg.strip(), -5, 100)
        elif cmd == "ttsmax":
            if arg.strip(): speak_tts(arg.strip(), 10, 100)
        elif cmd == "ttsmin":
            if arg.strip(): speak_tts(arg.strip(), -10, 100)
        elif cmd == "ttsloud":
            if arg.strip(): speak_tts(arg.strip(), 0, 100)
        elif cmd == "ttsquiet":
            if arg.strip(): speak_tts(arg.strip(), 0, 20)
        elif cmd == "ttswhisper":
            if arg.strip(): speak_tts(arg.strip(), -3, 15)
        elif cmd == "ttsspam":
            speak_tts("A" * 30, 8, 100)
        elif cmd == "ttsgibberish":
            gib = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(20))
            speak_tts(gib, 2, 100)
        elif cmd == "ttscount":
            speak_tts("1 2 3 4 5 6 7 8 9 10", 0, 100)
        elif cmd == "ttsreverse":
            if arg.strip(): speak_tts(arg.strip()[::-1], 0, 100)
        elif cmd == "ttslong":
            speak_tts("Did you know that in terms of male human and female pokemon breeding...", 3, 100)
        elif cmd == "ttssong":
            speak_tts("Never gonna give you up, never gonna let you down, never gonna run around and desert you", 0, 100)
        elif cmd == "ttsalarm":
            speak_tts("BEEP BEEP BEEP WARNING BEEP BEEP", 5, 100)
        elif cmd == "ttsscary":
            speak_tts("I am inside your walls. Look behind you.", -6, 100)
        elif cmd == "ttsmorse":
            speak_tts("dot dash dot dot dash dash dot", 0, 100)
        elif cmd == "ttsspell":
            if arg.strip():
                speak_tts("-".join(list(arg.strip())), -2, 100)
        elif cmd == "ttsquestion":
            if arg.strip(): speak_tts(arg.strip() + " ???", 0, 100)
        elif cmd == "ttsmath":
            speak_tts("two plus two is four minus one that's three quick maths", 2, 100)
        elif cmd == "ttsoof":
            speak_tts("oooooooooof", -3, 100)
        elif cmd == "help":
            cat = arg.strip().lower() if arg.strip() else ""
            if cat == "fun":
                type_output("fun: 8ball rps roll coinflip dice slot quote color rate choose hug slap flip jumble mock ascii reverse caps whisper typewriter duel roast compliment")
            elif cat == "chaos":
                type_output("chaos: maze disco jiggle spin earthquake afk panic scare spam rickroll countdown timer hack matrix alarm")
            elif cat == "mouse":
                type_output("mouse: move gamemove abs click rclick mclick drag scroll jiggle spin")
            elif cat == "media":
                type_output("media: volume play pause next prev mediastop brightnessup brightnessdown")
            elif cat == "window":
                type_output("window: alttab newtab closetab refresh fullscreen minimize maximize snapleft snapright desktop explorer settings alert clipboard emoji magnify unmagnify zoomin zoomout zoomreset")
            elif cat == "admin":
                type_output("admin: ban unban motd announce disable enable setcooldown pausechat enablechat clearfeed shutdown restartvm forcefixvm votestop opme stoptts disabletts enabletts")
            elif cat == "info":
                type_output("info: whoami leaderboard stats memory uptime ping help")
            elif cat == "social":
                type_output("social: hug slap duel roast compliment gift ship throw emote confess tpose")
            elif cat == "games":
                type_output("games: fish mine pet battle gamble heist roulette snake race lottery trivia fortune dare truth")
            elif cat == "text":
                type_output("text: uwu clap mock stretch censor echo rainbow repeat typewriter topbar chain progress password math percent poll")
            elif cat == "meme":
                type_output("meme: ppsize iq sus vibe inventory drop grab crime horoscope weather")
            elif cat == "voice":
                type_output("voice: tts ttsloop ttsfast ttsslow ttsmax ttsmin ttsloud ttsquiet ttswhisper ttsspam ttsgibberish ttscount ttsreverse ttslong ttssong ttsalarm ttsscary ttsmorse ttsspell ttsquestion ttsmath ttsoof")
            else:
                type_output("!help fun | chaos | mouse | media | window | admin | info | social | games | text | meme | voice")
    except Exception as e:
        total_commands_failed += 1
"""
exec(_CMD_STR, globals())
del _CMD_STR

# Load Danish Layout if needed
kb_lang = os.getenv('KEYBOARD', 'da').lower()
if kb_lang != 'us':
    try:
        from layout_win_da import KeyboardLayout
        layout = KeyboardLayout(kbd)
    except ImportError:
        pass

last_poll_time = 0
last_relay_rescan = 0.0
poll_interval = 0.1 if RELAY_URL else 1.0
relay_msg_index = 0
first_relay_poll = True   # skip messages already buffered before the Pico connected
serial_buffer = ""
last_err = ""

while True:
    # 1. Serial / USB console input — works in BOTH modes. In local-control
    #    mode this is how you test commands (e.g.  !combo win+r ).
    if supervisor.runtime.serial_bytes_available:
        char = sys.stdin.read(1)
        if char in ('\n', '\r'):
            cmd_str = serial_buffer.strip()
            if cmd_str:
                if not cmd_str.startswith(PREFIX):
                    cmd_str = PREFIX + cmd_str
                parse_and_run(cmd_str, "CONSOLE", True, True)
            serial_buffer = ""
        else:
            serial_buffer += char

    now = time.monotonic()

    # 2. If we have no relay yet, keep rescanning the LAN every 20s so the Pico
    #    auto-connects the moment relay_local.py comes online.
    if not RELAY_URL and pool is not None and (now - last_relay_rescan) >= 20.0:
        last_relay_rescan = now
        found = scan_relay_lan()
        if found:
            RELAY_URL = found
            first_relay_poll = True
            poll_interval = 0.1
            status("founded relay! now using relay")
            status(RELAY_URL)

    # 3. Relay chat poll (the only chat source in this build)
    if RELAY_URL and requests is not None and (now - last_poll_time) >= poll_interval:
        last_poll_time = now
        try:
            gc.collect()
            sep = "&" if "?" in RELAY_URL else "?"
            relay_full = RELAY_URL + sep + "after=" + str(relay_msg_index)
            response = requests.get(relay_full)
            try:
                data = response.json()
                new_total = data.get('total', relay_msg_index)
                if first_relay_poll:
                    # Skip the backlog that existed before we connected
                    first_relay_poll = False
                    relay_msg_index = new_total
                else:
                    for item in data.get('messages', []):
                        msg = item.get('text', '')
                        author = item.get('author', '?')
                        clean_author = author.lower().replace(" ", "")
                        is_mod = item.get('isMod', False)
                        is_owner_yt = item.get('isOwner', False)
                        is_owner = is_owner_yt or clean_author in OWNERS
                        is_admin = is_owner or is_mod or clean_author in ADMINS
                        if clean_author in BANNED_USERS or (chat_paused and not is_owner):
                            continue
                        is_cmd = msg.startswith(PREFIX)
                        feed_append(author, msg, is_cmd)
                        if is_cmd:
                            parse_and_run(msg, author, is_admin, is_owner)
                    relay_msg_index = new_total
                poll_interval = 0.1   # fast again on success
                last_err = ""
            finally:
                response.close()
        except Exception as e:
            es = str(e)
            if es != last_err:
                last_err = es
            # The relay may have gone away — drop back to scanning for it.
            poll_interval = min(poll_interval * 2, 5.0)
            if poll_interval >= 5.0:
                RELAY_URL = ""
                status("relay lost — rescanning")


    # 4. Web Dashboard
    tick_web()

    # 5. Vote Timeouts
    tick_votes()

    # 6. Periodic stats save
    if (now - last_stats_save) >= STATS_SAVE_INTERVAL:
        last_stats_save = now
        save_stats()

    # 7. Memory cleanup & yield
    if 'gc_loop_counter' not in dir():
        gc_loop_counter = 0
    gc_loop_counter += 1
    if gc_loop_counter >= 50:
        gc.collect()
        gc_loop_counter = 0
    time.sleep(0.001)