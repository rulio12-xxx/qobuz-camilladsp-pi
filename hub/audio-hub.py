#!/usr/bin/env python3
"""Centre de controle de la chaine audio — page unique a onglets.
Onglets : Statuts / Radios / Lampes / CamillaGUI / Qobuz.
Sert sur le port 8080.
"""

import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8080
LOGO_DIR = os.path.expanduser("~/radio/logos")
USB_DEV = "3-2"
HWPARAMS = "/proc/asound/card10/pcm0p/sub0/hw_params"
TUBE_LEVEL_FILE = "/home/rulio12/tube/tube.level"
APPLY_TUBE = "/home/rulio12/tube/apply_tube.sh"

SERVICES = ["camilladsp", "qobuz-proxy", "audio-power", "camillagui", "mpd"]

STATIONS = [
    ("franceinter",   "France Inter",   "http://icecast.radiofrance.fr/franceinter-hifi.aac"),
    ("franceculture", "France Culture", "http://icecast.radiofrance.fr/franceculture-hifi.aac"),
    ("fip",           "FIP",            "http://icecast.radiofrance.fr/fip-hifi.aac"),
    ("fipjazz",       "FIP Jazz",       "http://icecast.radiofrance.fr/fipjazz-hifi.aac"),
    ("tsfjazz",       "TSF Jazz",       "http://broadcast.infomaniak.ch/tsfjazz-high.mp3"),
    ("nova",          "Radio Nova",     "http://radionova.ice.infomaniak.ch/radionova-256.aac"),
    ("franceinfo",    "France Info",    "http://icecast.radiofrance.fr/franceinfo-hifi.aac"),
    ("nostalgie",     "Nostalgie",      "http://cdn.nrjaudio.fm/audio1/fr/30601/mp3_128.mp3"),
    ("bfm",           "BFM",            "http://audio.bfmtv.com/rmcradio_128.mp3"),
]

RESTARTABLE = {"camilladsp", "qobuz-proxy", "audio-power", "camillagui", "radio"}

TUBE_LABELS = {"0": "Off", "1": "Leger", "2": "Moyen", "3": "Fort"}


def mpc(*args):
    return subprocess.run(["mpc", *args], capture_output=True, text=True).stdout.strip()


def svc_active(name):
    return subprocess.run(["systemctl", "is-active", "--quiet", name]).returncode == 0


def bluetooth_status():
    import re
    try:
        pcms = subprocess.run(["bluealsactl", "list-pcms"],
                              capture_output=True, text=True, timeout=5).stdout
        for path in pcms.splitlines():
            path = path.strip()
            if "a2dpsnk/source" not in path:
                continue
            info = subprocess.run(["bluealsactl", "info", path],
                                  capture_output=True, text=True, timeout=5).stdout
            playing = "Running: true" in info
            name = None
            m = re.search(r"dev_([0-9A-F_]+)/", path)
            if m:
                mac = m.group(1).replace("_", ":")
                devs = subprocess.run(["bluetoothctl", "devices", "Connected"],
                                      capture_output=True, text=True, timeout=5).stdout
                for line in devs.splitlines():
                    p = line.strip().split(" ", 2)
                    if len(p) == 3 and p[1].upper() == mac.upper():
                        name = p[2]
            return {"name": name or "appareil", "playing": playing}
    except Exception:
        pass
    return None


def tube_level():
    try:
        lvl = open(TUBE_LEVEL_FILE).read().strip()
        return lvl if lvl in TUBE_LABELS else "0"
    except OSError:
        return "0"


def set_tube(level):
    if level not in TUBE_LABELS:
        return
    subprocess.run([APPLY_TUBE, level], capture_output=True, timeout=40)
    subprocess.run(["sudo", "systemctl", "restart", "camilladsp"])


def status_json():
    import json
    services = {s: ("active" if svc_active(s) else "inactive") for s in SERVICES}
    dac = os.path.exists(f"/sys/bus/usb/devices/{USB_DEV}")
    loopback, rate = False, None
    try:
        txt = open(HWPARAMS).read()
        if "closed" not in txt:
            loopback = True
            import re
            m = re.search(r"rate:\s*(\d+)", txt)
            rate = int(m.group(1)) if m else None
    except OSError:
        pass
    np = None
    try:
        if "playing" in mpc("status"):
            title = mpc("-f", "%title%", "current")
            name = mpc("-f", "%name%", "current")
            if title and name:
                np = name + " — " + title
            elif title:
                np = title
            elif name:
                np = name
            else:
                np = "en lecture"
    except Exception:
        pass
    vol = {"dac": dac_volume(), "cdsp": cdsp_volume(), "qobuz": qobuz_volume()}
    return json.dumps({"services": services, "dac": dac, "loopback": loopback,
                       "rate": rate, "now_playing": np,
                       "bluetooth": bluetooth_status(), "tube": tube_level(),
                       "loud": loud_enabled(),
                       "vol": vol})


VENV_PY = "/home/rulio12/audio-power/venv/bin/python3"
DAC_CTL = "DX5 II"


def dac_volume(db=None):
    """Lit (db=None) ou regle le volume du DAC, en dB."""
    import re as _re
    if db is not None:
        subprocess.run(["amixer", "-c", "II", "sset", DAC_CTL, "--", f"{db}dB"],
                       capture_output=True)
    out = subprocess.run(["amixer", "-c", "II", "sget", DAC_CTL],
                         capture_output=True, text=True).stdout
    m = _re.search(r"\[(-?\d+\.\d+)dB\]", out)
    return float(m.group(1)) if m else None


def cdsp_volume(db=None):
    """Lit ou regle le volume principal de CamillaDSP, en dB."""
    code = "from camilladsp import CamillaClient\n"
    code += "c=CamillaClient('127.0.0.1',1234)\nc.connect()\n"
    if db is not None:
        code += f"c.volume.set_main_volume({db})\n"
    code += "print(c.volume.main_volume())\n"
    try:
        r = subprocess.run([VENV_PY, "-c", code], capture_output=True,
                           text=True, timeout=5)
        return float(r.stdout.strip())
    except Exception:
        return None


def qobuz_volume():
    """Derniere valeur de volume vue dans les logs du proxy (0-100)."""
    import re as _re
    try:
        out = subprocess.run(["journalctl", "-u", "qobuz-proxy", "-n", "400",
                              "-o", "cat"], capture_output=True, text=True,
                             timeout=5).stdout
    except Exception:
        return None
    vals = _re.findall(r"Volume set to (\d+)|volume to app: (\d+)%", out)
    for a, b in reversed(vals):
        return int(a or b)
    return None


LOUD_FLAG = "/home/rulio12/loudness/enabled"


def loud_enabled():
    return os.path.exists(LOUD_FLAG)


def set_loud(on):
    if on:
        open(LOUD_FLAG, "w").close()
    elif os.path.exists(LOUD_FLAG):
        os.remove(LOUD_FLAG)


def do_action(name):
    if name in RESTARTABLE:
        subprocess.run(["sudo", "systemctl", "restart", name])
        return True
    return False


def radio_play(url):
    mpc("clear"); mpc("add", url); mpc("play")


def radio_stop():
    mpc("stop")


PAGE = """<!DOCTYPE html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chaine audio</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#16324F">
<meta name="mobile-web-app-capable" content="yes"><style>
:root{--bg:#16324F;--ac:#2A9D8F;--ko:#C62828;--warn:#E9A03B;}
*{box-sizing:border-box;margin:0;font-family:system-ui,sans-serif;}
body{background:#f4f7f7;height:100vh;display:flex;flex-direction:column;}
header{background:var(--bg);color:#fff;padding:12px 16px;font-size:16px;font-weight:600;}
nav{display:flex;background:#0e2438;flex-wrap:wrap;}
nav button{flex:1;border:0;padding:12px 4px;font-size:13px;cursor:pointer;
   background:transparent;color:#9fb6c9;min-width:70px;}
nav button.active{background:#f4f7f7;color:var(--bg);font-weight:700;border-radius:8px 8px 0 0;}
.tab{display:none;flex:1;overflow:auto;padding:14px;}
.tab.active{display:block;}
.tab.frame{padding:0;}
iframe{border:0;width:100%;height:100%;background:#fff;}
.card{background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:12px 14px;margin-bottom:10px;
   display:flex;align-items:center;gap:12px;}
.dot{width:11px;height:11px;border-radius:50%;background:#888;flex-shrink:0;}
.ok .dot{background:var(--ac);}.ko .dot{background:var(--ko);}.warn .dot{background:var(--warn);}
.card .name{flex:1;font-weight:600;color:var(--bg);}
.card button{background:var(--bg);color:#fff;border:0;border-radius:8px;padding:8px 14px;
   font-size:13px;cursor:pointer;}
.hw{display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap;}
.pill{display:inline-flex;align-items:center;gap:7px;font-size:13px;background:#fff;
   border:1px solid #e0e0e0;border-radius:999px;padding:7px 13px;}
#stations{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;}
.st{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
   text-align:center;background:#fff;border:1px solid #ddd;border-radius:10px;padding:12px 6px;
   font-size:13px;cursor:pointer;color:var(--bg);font-weight:600;}
.st img{width:56px;height:56px;object-fit:contain;border-radius:8px;}
.st:active{background:var(--ac);color:#fff;}
.stop{background:var(--ko);color:#fff;border:0;justify-content:center;width:100%;font-size:16px;}
.np{background:var(--ac);color:#fff;padding:12px;border-radius:10px;font-weight:600;margin-bottom:14px;}
.np.off{background:#999;}
.volrow{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid #e0e0e0;
   border-radius:10px;padding:10px 12px;margin-bottom:8px;}
.vollab{width:64px;font-weight:700;color:var(--bg);font-size:13px;}
.volrow input[type=range]{flex:1;}
.volval{width:66px;text-align:right;font-size:13px;color:var(--bg);font-weight:600;}
.tuberow{display:flex;gap:8px;}
.tubebtn{flex:1;text-align:center;background:#fff;border:2px solid #ddd;
   border-radius:10px;padding:12px 4px;font-size:15px;cursor:pointer;
   color:var(--bg);font-weight:700;}
.tubebtn.sel{background:var(--ac);color:#fff;border-color:var(--ac);}
.tubeinfo{background:var(--bg);color:#fff;padding:12px;border-radius:10px;margin-bottom:16px;
   font-weight:600;text-align:center;}
</style></head><body>
<nav>
  <button id="t0" class="active" onclick="tab(0)">Statuts</button>
  <button id="t1" onclick="tab(1)">Radios</button>
  <button id="t5" onclick="tab(5)">Musique</button>
  <button id="t2" onclick="tab(2)">CamillaGUI</button>
  <button id="t3" onclick="tab(3)">Qobuz</button>
</nav>

<div id="p0" class="tab active">
  <div class="hw" id="hw"></div>
  <div id="services"></div>
  <div class="volrow"><span class="vollab">DAC</span>
    <input type="range" id="vdac" min="-60" max="0" step="0.5"
      oninput="vshow('vdac',this.value)" onchange="vset('dac',this.value)">
    <span class="volval" id="vdacv">&ndash;</span></div>
  <div class="volrow"><span class="vollab">Camilla</span>
    <input type="range" id="vcdsp" min="-40" max="0" step="0.5"
      oninput="vshow('vcdsp',this.value)" onchange="vset('cdsp',this.value)">
    <span class="volval" id="vcdspv">&ndash;</span></div>
  <div class="volrow"><span class="vollab">Qobuz</span>
    <span style="flex:1;font-size:12px;color:#888;">pilot&#233; depuis l'app</span>
    <span class="volval" id="vqobuzv">&ndash;</span></div>
  <div class="tuberow">
    <button class="tubebtn" id="tube0" onclick="setTube('0')">Lampes Off</button>
    <button class="tubebtn" id="tube3" onclick="setTube('3')">Lampes On</button>
    <button class="tubebtn" id="loud0" onclick="setLoud(0)">Loudness Off</button>
    <button class="tubebtn" id="loud1" onclick="setLoud(1)">Loudness On</button>
  </div>
</div>

<div id="p1" class="tab">
  <div id="np" class="np off">arr&#234;t&#233;</div>
  <div id="stations"></div>
  <button class="st stop" onclick="rstop()">&#9632; Arr&#234;ter (revenir &#224; Qobuz)</button>
</div>

<div id="p5" class="tab frame"><iframe id="if5"></iframe></div>
<div id="p2" class="tab frame"><iframe id="if2"></iframe></div>
<div id="p3" class="tab frame"><iframe id="if3"></iframe></div>

<script>
const H=location.hostname;
const STATIONS=__STATIONS__;
const TUBELABELS={"0":"Off","1":"L\\u00e9ger","2":"Moyen","3":"Fort"};
let framesLoaded={2:false,3:false,5:false};
function tab(i){
  for(const n of [0,1,2,3,5]){
    document.getElementById('t'+n).classList.toggle('active',n===i);
    document.getElementById('p'+n).classList.toggle('active',n===i);
  }
  if(i===2&&!framesLoaded[2]){document.getElementById('if2').src='http://'+H+':5005';framesLoaded[2]=true;}
  if(i===3&&!framesLoaded[3]){document.getElementById('if3').src='http://'+H+':8689';framesLoaded[3]=true;}
  if(i===5&&!framesLoaded[5]){document.getElementById('if5').src='http://'+H+':8082';framesLoaded[5]=true;}
}
function stationsHtml(){
  let h='';
  for(const [sid,name,url] of STATIONS){
    h+='<button class="st" onclick="rplay(\\''+url+'\\')">'+
       '<img src="/logo?id='+sid+'" onerror="this.style.display=\\'none\\'">'+
       '<span>'+name+'</span></button>';
  }
  document.getElementById('stations').innerHTML=h;
}
async function refresh(){
  try{
    const s=await (await fetch('/status')).json();
    let hw='';
    hw+='<span class="pill '+(s.dac?'ok':'warn')+'"><span class="dot"></span>DAC '+(s.dac?'pr\\u00e9sent':'veille')+'</span>';
    hw+='<span class="pill '+(s.loopback?'ok':'warn')+'"><span class="dot"></span>flux '+(s.loopback?(s.rate+' Hz'):'inactif')+'</span>';
    if(s.bluetooth){var bt=s.bluetooth;hw+='<span class="pill '+(bt.playing?'ok':'warn')+'"><span class="dot"></span>'+(bt.playing?'\\u25b6 BT: ':'BT: ')+bt.name+(bt.playing?'':' (connect\\u00e9)')+'</span>';}
    if(s.tube&&s.tube!=='0'){hw+='<span class="pill ok"><span class="dot"></span>Lampes: '+TUBELABELS[s.tube]+'</span>';}
    document.getElementById('hw').innerHTML=hw;
    let sv='';
    for(const [name,state] of Object.entries(s.services)){
      const ok=state==='active';
      sv+='<div class="card '+(ok?'ok':'ko')+'"><span class="dot"></span>'+
          '<span class="name">'+name+'</span>'+
          '<button onclick="act(\\''+name+'\\')">'+(ok?'Red\\u00e9marrer':'D\\u00e9marrer')+'</button></div>';
    }
    document.getElementById('services').innerHTML=sv;
    const np=document.getElementById('np');
    if(s.now_playing){np.className='np';np.textContent='\\u25b6 '+s.now_playing;}
    else{np.className='np off';np.textContent='arr\\u00eat\\u00e9';}
    // lampes : marquer le niveau actif
    for(const n of ['0','3']){
      document.getElementById('tube'+n).classList.toggle('sel', s.tube===n);
    }
    document.getElementById('loud0').classList.toggle('sel', !s.loud);
    document.getElementById('loud1').classList.toggle('sel', !!s.loud);
    if(s.vol){vmaj('vdac',s.vol.dac);vmaj('vcdsp',s.vol.cdsp);
      document.getElementById('vqobuzv').textContent=(s.vol.qobuz==null?'\u2013':s.vol.qobuz+'%');}
  }catch(e){}
}
function vshow(id,v){document.getElementById(id+'v').textContent=Number(v).toFixed(1)+' dB';}
function vmaj(id,v){if(v==null)return;const e=document.getElementById(id);
  if(document.activeElement!==e)e.value=v; vshow(id,v);}
async function vset(t,v){await fetch('/vol?t='+t+'&db='+v);}
async function act(n){await fetch('/action?svc='+n);setTimeout(refresh,1500);}
async function rplay(u){await fetch('/play?url='+encodeURIComponent(u));setTimeout(refresh,1500);}
async function rstop(){await fetch('/stop');setTimeout(refresh,1500);}
async function setLoud(v){await fetch('/loud?on='+v);setTimeout(refresh,800);}
async function setTube(l){
  await fetch('/tube?level='+l);setTimeout(refresh,3000);
}
stationsHtml();refresh();setInterval(refresh,5000);
</script></body></html>"""


ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" fill="#16324F"/>
<path d="M256 112c-70 0-128 56-128 126v66a24 24 0 0 0 24 24h28a20 20 0 0 0 20-20v-72a20 20 0 0 0-20-20h-28v22c0-57 46-104 104-104s104 47 104 104v-22h-28a20 20 0 0 0-20 20v72a20 20 0 0 0 20 20h28a24 24 0 0 0 24-24v-66c0-70-58-126-128-126z" fill="#2A9D8F"/>
</svg>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/status":
            self._send(200, "application/json", status_json().encode())
        elif u.path == "/action":
            do_action(q.get("svc", [""])[0])
            self._send(200, "text/plain", b"ok")
        elif u.path == "/loud":
            set_loud(q.get("on", ["0"])[0] == "1")
            self._send(200, "text/plain", b"ok")
        elif u.path == "/vol":
            t = q.get("t", [""])[0]
            try:
                db = float(q.get("db", ["0"])[0])
            except ValueError:
                db = None
            if db is not None and -80 <= db <= 0:
                if t == "dac":
                    dac_volume(db)
                elif t == "cdsp":
                    cdsp_volume(db)
            self._send(200, "text/plain", b"ok")
        elif u.path == "/tube":
            set_tube(q.get("level", ["0"])[0])
            self._send(200, "text/plain", b"ok")
        elif u.path == "/play":
            if "url" in q: radio_play(q["url"][0])
            self._send(200, "text/plain", b"ok")
        elif u.path == "/stop":
            radio_stop(); self._send(200, "text/plain", b"ok")
        elif u.path == "/manifest.json":
            import json as _j
            mf = _j.dumps({"name": "Chaine audio", "short_name": "Audio",
                           "start_url": "/", "display": "fullscreen",
                           "background_color": "#f4f7f7", "theme_color": "#16324F",
                           "icons": [{"src": "/icon.svg", "sizes": "any",
                                      "type": "image/svg+xml", "purpose": "any maskable"}]})
            self._send(200, "application/manifest+json", mf.encode())
        elif u.path == "/icon.svg":
            self._send(200, "image/svg+xml", ICON_SVG.encode())
        elif u.path == "/logo":
            sid = q.get("id", [""])[0]
            path = os.path.join(LOGO_DIR, sid + ".png")
            if os.path.isfile(path):
                with open(path, "rb") as f: self._send(200, "image/png", f.read())
            else:
                self._send(404, "text/plain", b"no")
        else:
            import json
            body = PAGE.replace("__STATIONS__", json.dumps(STATIONS))
            self._send(200, "text/html; charset=utf-8", body.encode())

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

