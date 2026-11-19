"""Client HTTP minimal pour un Shelly a un relais (gen1 et gen2+/gen3)."""
import json
import urllib.request


def _get(url, timeout=3):
    req = urllib.request.Request(url, headers={"User-Agent": "domotique/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(16384).decode("utf-8", "replace"))


def status(ip, gen=2, channel=0):
    """-> {"output": bool, "power": float|None}. Leve une exception si injoignable."""
    if int(gen) >= 2:
        j = _get(f"http://{ip}/rpc/Switch.GetStatus?id={channel}")
        return {"output": bool(j["output"]), "power": j.get("apower")}
    j = _get(f"http://{ip}/relay/{channel}")
    return {"output": bool(j["ison"]), "power": None}


def set_output(ip, on, gen=2, channel=0):
    """Allume/eteint le relais. Leve une exception en cas d'echec."""
    if int(gen) >= 2:
        _get(f"http://{ip}/rpc/Switch.Set?id={channel}&on={'true' if on else 'false'}")
    else:
        _get(f"http://{ip}/relay/{channel}?turn={'on' if on else 'off'}")
