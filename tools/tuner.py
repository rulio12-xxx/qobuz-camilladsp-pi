#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8090
try:
    from camilladsp import CamillaClient as _C
    NEW = True
except ImportError:
    from camilladsp import CamillaConnection as _C
    NEW = False

def cdsp():
    c = _C("127.0.0.1", 1234); c.connect(); return c

def get(c): return c.config.active() if NEW else c.get_config()
def put(c, cfg):
    c.config.set_active(cfg) if NEW else c.set_config(cfg)

def read(cfg):
    f = cfg["filters"]
    return (f["delay_R"]["parameters"]["delay"]
            - f["delay_L"]["parameters"]["delay"])

def write(cfg, d):
    d = max(-2.0, min(2.0, round(d, 3)))
    cfg["filters"]["delay_L"]["parameters"]["delay"] = max(0.0, -d)
    cfg["filters"]["delay_R"]["parameters"]["delay"] = max(0.0, d)
    return d

B = [-0.5, -0.2, -0.1, -0.05, 0.05, 0.1, 0.2, 0.5]

def page(d):
    if abs(d) < 0.001: txt = "aligne (0 ms)"
    elif d > 0:        txt = f"R retardee de {d:.3f} ms"
    else:              txt = f"L retardee de {-d:.3f} ms"
    btn = "".join(
        f'<a href="/s?v={x}">{x:+g}</a>' for x in B)
    return f"""<!doctype html><meta name=viewport
content="width=device-width,initial-scale=1">
<style>body{{background:#111;color:#eee;font:16px system-ui;
text-align:center;padding:1em}}
h1{{font-size:1.4em;font-weight:500}}
a{{display:inline-block;background:#264;color:#fff;
text-decoration:none;padding:.9em 0;margin:.3em;width:4.2em;
border-radius:.4em;font-size:1.2em}}
.z{{background:#642;width:9em}}
p{{color:#8b8;font-size:.85em}}</style>
<h1>{txt}</h1><div>{btn}</div>
<div><a class=z href="/s?v=0&abs=1">remettre a 0</a></div>
<p>{d*34.3:+.1f} cm equivalent</p>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        c = cdsp(); cfg = get(c); d = read(cfg)
        if u.path == "/s":
            v = float(q.get("v", ["0"])[0])
            d = write(cfg, v if q.get("abs") else d + v)
            put(c, cfg)
        body = page(d).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

HTTPServer(("0.0.0.0", PORT), H).serve_forever()
