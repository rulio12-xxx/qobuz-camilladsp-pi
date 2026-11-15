"""Detection des appareils du reseau : Shelly, Reolink, Bluetooth (BLE).

Methodes :
  * mDNS (zeroconf) : les Shelly annoncent _shelly._tcp / _http._tcp
  * scan actif du sous-reseau : sonde HTTP /shelly (Shelly gen1/gen2+) et
    /api.cgi?cmd=GetDevInfo (Reolink) -- fonctionne sans multicast
  * ONVIF WS-Discovery (multicast UDP) : camera Reolink
  * BLE (bleak) : appareils Bluetooth a proximite
"""
import asyncio
import ipaddress
import json
import logging
import re
import socket
import time
import urllib.request

log = logging.getLogger("discovery")

WS_DISCOVERY = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
    'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
    'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
    'xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
    '<e:Header><w:MessageID>uuid:84ede3de-7dec-11d0-c360-f01234567890</w:MessageID>'
    '<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
    '<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header>'
    '<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>'
    '</e:Envelope>'
)


class Registry:
    """Annuaire des appareils vus. `on_change(device)` est appele a chaque maj."""

    def __init__(self, on_change=None):
        self.devices = {}
        self.on_change = on_change

    def upsert(self, dev_id, **fields):
        now = int(time.time())
        d = self.devices.setdefault(dev_id, {"id": dev_id, "first_seen": now})
        changed = any(d.get(k) != v for k, v in fields.items() if v is not None)
        d.update({k: v for k, v in fields.items() if v is not None})
        d["last_seen"] = now
        if (changed or d.get("_new", True)) and self.on_change:
            d["_new"] = False
            self.on_change(d)
        return d

    def snapshot(self):
        return sorted(
            ({k: v for k, v in d.items() if not k.startswith("_")} for d in self.devices.values()),
            key=lambda d: (d["kind"], d.get("ip", ""), d["id"]),
        )


def _http_get(url, timeout=1.5):
    req = urllib.request.Request(url, headers={"User-Agent": "domotique/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(8192).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:  # 401 : un Shelly protege repond quand meme
        return e.code, e.read(4096).decode("utf-8", "replace")
    except Exception:
        return None, ""


def probe_host(ip):
    """Retourne (kind, fields) si `ip` est un Shelly ou une Reolink, sinon None."""
    st, body = _http_get(f"http://{ip}/shelly")
    if st == 200:
        try:
            j = json.loads(body)
        except ValueError:
            j = {}
        # gen2+ : {"id","mac","model","gen",...}  gen1 : {"type","mac","auth"...}
        if "mac" in j and ("type" in j or "model" in j or "app" in j):
            mac = j["mac"].lower()
            return "shelly", {
                "name": j.get("name") or j.get("id") or f"shelly-{mac[-6:]}",
                "model": j.get("model") or j.get("type"),
                "mac": mac,
                "ip": ip,
                "gen": j.get("gen", 1),
                "auth": bool(j.get("auth") or j.get("auth_en")),
                "firmware": j.get("ver") or j.get("fw"),
            }
    st, body = _http_get(f"http://{ip}/api.cgi?cmd=GetDevInfo")
    if st in (200, 401, 400) and '"cmd"' in body and "GetDevInfo" in body:
        # Reolink repond meme sans identifiants (erreur "please login first")
        info = {}
        try:
            info = json.loads(body)[0].get("value", {}).get("DevInfo", {})
        except Exception:
            pass
        return "reolink", {
            "name": info.get("name") or f"reolink-{ip}",
            "model": info.get("model"),
            "ip": ip,
            "firmware": info.get("firmVer"),
            "serial": info.get("serial"),
        }
    return None


def local_subnet():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ipaddress.ip_network(f"{ip}/24", strict=False)


async def scan_subnet(registry, subnet=None, concurrency=64):
    net = ipaddress.ip_network(subnet, strict=False) if subnet else local_subnet()
    if net.num_addresses > 1024:
        log.warning("sous-reseau %s trop large, scan limite", net)
        return
    sem = asyncio.Semaphore(concurrency)
    loop = asyncio.get_running_loop()

    async def one(ip):
        async with sem:
            res = await loop.run_in_executor(None, probe_host, str(ip))
        if res:
            kind, f = res
            dev_id = f"{kind}-{(f.get('mac') or f.get('serial') or f['ip']).replace(':', '')}"
            registry.upsert(dev_id, kind=kind, **f)

    await asyncio.gather(*(one(ip) for ip in net.hosts()))
    log.info("scan %s termine : %d appareil(s)", net, len(registry.devices))


async def onvif_discovery(registry, wait=3.0):
    """WS-Discovery : repere les cameras ONVIF, puis verifie si Reolink."""
    loop = asyncio.get_running_loop()
    found = set()

    class Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            m = re.search(rb"https?://([\d.]+)[:/]", data)
            ip = m.group(1).decode() if m else addr[0]
            found.add((ip, b"reolink" in data.lower()))

    try:
        transport, _ = await loop.create_datagram_endpoint(
            Proto, family=socket.AF_INET, allow_broadcast=True, local_addr=("0.0.0.0", 0))
    except OSError as e:
        log.warning("ONVIF indisponible : %s", e)
        return
    transport.sendto(WS_DISCOVERY.encode(), ("239.255.255.250", 3702))
    await asyncio.sleep(wait)
    transport.close()
    for ip, is_reolink in found:
        res = await loop.run_in_executor(None, probe_host, ip)
        if res and res[0] == "reolink":
            kind, f = res
            registry.upsert(f"reolink-{(f.get('serial') or ip)}", kind=kind, onvif=True, **f)
        elif is_reolink:
            registry.upsert(f"reolink-{ip}", kind="reolink", name=f"reolink-{ip}", ip=ip, onvif=True)
        else:
            registry.upsert(f"onvif-{ip}", kind="camera", name=f"camera-{ip}", ip=ip, onvif=True)


async def start_mdns(registry):
    """Ecoute mDNS en continu (Shelly annonce _shelly._tcp et _http._tcp)."""
    try:
        from zeroconf import ServiceStateChange
        from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
    except ImportError:
        log.warning("zeroconf absent : mDNS desactive")
        return None
    azc = AsyncZeroconf()
    loop = asyncio.get_running_loop()

    async def resolve(stype, name):
        info = await azc.async_get_service_info(stype, name, 3000)
        if not info or not info.addresses:
            return
        ip = socket.inet_ntoa(info.addresses[0])
        res = await loop.run_in_executor(None, probe_host, ip)
        if res:
            kind, f = res
            dev_id = f"{kind}-{(f.get('mac') or f.get('serial') or ip).replace(':', '')}"
            registry.upsert(dev_id, kind=kind, **f)

    def handler(zeroconf, service_type, name, state_change):
        if state_change in (ServiceStateChange.Added, ServiceStateChange.Updated):
            if service_type.startswith("_shelly") or name.lower().startswith(("shelly", "reolink")):
                asyncio.ensure_future(resolve(service_type, name))

    browser = AsyncServiceBrowser(
        azc.zeroconf, ["_shelly._tcp.local.", "_http._tcp.local."], handlers=[handler])
    return azc, browser


async def ble_scan(registry, duration=8.0):
    try:
        from bleak import BleakScanner
    except ImportError:
        return
    try:
        found = await BleakScanner.discover(timeout=duration, return_adv=True)
    except Exception as e:
        log.warning("scan BLE impossible : %s", e)
        return
    for addr, (dev, adv) in found.items():
        registry.upsert(
            f"ble-{addr.replace(':', '').lower()}", kind="ble", mac=addr.lower(),
            name=adv.local_name or dev.name or "(sans nom)", rssi=adv.rssi)
