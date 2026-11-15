"""Serveur domotique : detection + publication MQTT + interface web simplifiee."""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import paho.mqtt.client as mqtt
import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import discovery
from tariff import Tariff

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("domotique")

E = os.environ.get
BASE = E("MQTT_BASE", "domotique")
SCAN_INTERVAL = int(E("SCAN_INTERVAL", "300"))
STATIC = Path(__file__).parent / "static"

mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="domotique-server")
if E("MQTT_USER"):
    mq.username_pw_set(E("MQTT_USER"), E("MQTT_PASSWORD"))
mq.will_set(f"{BASE}/status", "offline", retain=True)


def publish(device):
    pub = {k: v for k, v in device.items() if not k.startswith("_")}
    mq.publish(f"{BASE}/devices/{device['id']}", json.dumps(pub), retain=True)


registry = discovery.Registry(on_change=publish)

TARIFF_FILE = Path(E("TARIFF_FILE", Path(__file__).parent.parent / "tariff.json"))
tariff = None
try:
    tariff = Tariff.load(TARIFF_FILE)
except FileNotFoundError:
    log.warning("%s absent : copier tariff.example.json en tariff.json", TARIFF_FILE)
except Exception:
    log.exception("tarif illisible")


async def loop_tariff():
    """Publie la periode HP/HC (retenue) a chaque changement."""
    last = None
    while True:
        if tariff:
            n = tariff.now(time.time())
            if n["period"] != last:
                last = n["period"]
                mq.publish(f"{BASE}/tariff", json.dumps(n), retain=True)
                log.info("periode tarifaire : %s", last)
        await asyncio.sleep(30)


async def scan_all():
    await asyncio.gather(
        discovery.scan_subnet(registry, E("SCAN_SUBNET") or None),
        discovery.onvif_discovery(registry),
    )
    if E("BLE_SCAN", "1") == "1":
        await discovery.ble_scan(registry)


async def loop_scan():
    while True:
        try:
            await scan_all()
        except Exception:
            log.exception("erreur de scan")
        await asyncio.sleep(SCAN_INTERVAL)


@asynccontextmanager
async def lifespan(app):
    try:
        mq.connect_async(E("MQTT_HOST", "127.0.0.1"), int(E("MQTT_PORT", "1883")))
        mq.loop_start()
        mq.publish(f"{BASE}/status", "online", retain=True)
    except Exception:
        log.exception("MQTT indisponible, on continue sans")
    mdns = await discovery.start_mdns(registry)
    tasks = [asyncio.create_task(loop_scan()), asyncio.create_task(loop_tariff())]
    yield
    for t in tasks:
        t.cancel()
    if mdns:
        await mdns[0].async_close()
    mq.publish(f"{BASE}/status", "offline", retain=True)
    mq.loop_stop()


app = FastAPI(title="Domotique", lifespan=lifespan)


@app.get("/api/devices")
def devices():
    return registry.snapshot()


@app.get("/api/config")
def config():
    return {"frigate_url": E("FRIGATE_URL", "http://localhost:5000")}


@app.get("/api/tariff")
def tariff_now():
    if not tariff:
        raise HTTPException(503, "tariff.json absent")
    return tariff.now(time.time())


@app.post("/api/tariff/report")
def tariff_report(body: dict = Body(...)):
    """{"intervals": [[start_ts, end_ts, kwh], ...], "export_kwh": 0} -> couts et economies."""
    if not tariff:
        raise HTTPException(503, "tariff.json absent")
    try:
        iv = [(float(a), float(b), float(k)) for a, b, k in body["intervals"]]
        return tariff.report(iv, float(body.get("export_kwh", 0)))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(422, "format : {intervals: [[start_ts, end_ts, kwh], ...]}")


@app.post("/api/scan")
async def scan():
    await scan_all()
    return JSONResponse({"count": len(registry.devices)})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(E("WEB_PORT", "8080")))
