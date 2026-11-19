"""Pilotage des Shelly : manuel (clic) ou automatique (suit les heures creuses).

Securite par conception :
  * mode par defaut = "manuel" : rien n'agit seul tant qu'on n'a pas choisi "auto"
  * "auto" refuse si le tarif (heures creuses) n'est pas configure
  * si le Shelly est injoignable ou le tarif absent, on n'agit pas (aucune commande a l'aveugle)
  * chaque action est journalisee (state/actions.jsonl) pour verifier le comportement
"""
import asyncio
import json
import logging
import time
from pathlib import Path

import shelly

log = logging.getLogger("control")
MODES = ("manual", "auto")


class ControlError(Exception):
    pass


class Controller:
    def __init__(self, registry, get_tariff, publish, state_dir, base="domotique"):
        self.registry = registry
        self.get_tariff = get_tariff
        self.publish = publish            # publish(topic, payload, retain)
        self.base = base
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.dir / "control.json"
        self.log_file = self.dir / "actions.jsonl"
        self.modes = self._load()
        self.cache = {}                   # dev_id -> dernier etat lu
        self._unreachable = set()

    # -- persistance ------------------------------------------------------
    def _load(self):
        try:
            return {k: v for k, v in json.loads(self.state_file.read_text()).items() if v in MODES}
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.state_file.write_text(json.dumps(self.modes))

    def _log(self, dev_id, event, **kw):
        rec = {"ts": int(time.time()), "time": time.strftime("%F %T"), "device": dev_id, "event": event, **kw}
        with self.log_file.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        log.info("%s %s %s", dev_id, event, kw or "")

    def tail_log(self, n=50):
        try:
            lines = self.log_file.read_text().splitlines()[-n:]
        except OSError:
            return []
        return [json.loads(x) for x in lines if x.strip()]

    # -- appareils --------------------------------------------------------
    def _dev(self, dev_id):
        d = self.registry.devices.get(dev_id)
        if not d or d.get("kind") != "shelly" or not d.get("ip"):
            raise ControlError(f"appareil {dev_id} inconnu ou sans adresse")
        return d

    async def _run(self, fn, *a, **k):
        return await asyncio.get_running_loop().run_in_executor(None, lambda: fn(*a, **k))

    async def read(self, dev_id):
        d = self._dev(dev_id)
        try:
            st = await self._run(shelly.status, d["ip"], d.get("gen", 2))
        except Exception as e:
            if dev_id not in self._unreachable:
                self._unreachable.add(dev_id)
                self._log(dev_id, "injoignable", erreur=str(e)[:100])
            self.cache[dev_id] = {"online": False}
            return self.cache[dev_id]
        if dev_id in self._unreachable:
            self._unreachable.discard(dev_id)
            self._log(dev_id, "de_nouveau_joignable")
        self.cache[dev_id] = {"online": True, **st}
        return self.cache[dev_id]

    async def _set(self, dev_id, on, source):
        d = self._dev(dev_id)
        try:
            await self._run(shelly.set_output, d["ip"], on, d.get("gen", 2))
        except Exception as e:
            self._log(dev_id, "echec_commande", on=on, source=source, erreur=str(e)[:100])
            raise ControlError(f"commande impossible : {e}")
        self.cache[dev_id] = {**self.cache.get(dev_id, {}), "online": True, "output": on}
        self._log(dev_id, "commande", on=on, source=source)
        self._publish_state(dev_id)

    def _publish_state(self, dev_id):
        c = self.cache.get(dev_id, {})
        self.publish(f"{self.base}/control/{dev_id}/state",
                     json.dumps({"mode": self.mode(dev_id), "online": c.get("online", False),
                                 "output": c.get("output")}), True)

    # -- API --------------------------------------------------------------
    def mode(self, dev_id):
        return self.modes.get(dev_id, "manual")

    def set_mode(self, dev_id, mode):
        if mode not in MODES:
            raise ControlError("mode : manual ou auto")
        self._dev(dev_id)
        if mode == "auto" and not self.get_tariff():
            raise ControlError("mode auto impossible : tariff.json (heures creuses) absent")
        if self.modes.get(dev_id) != mode:
            self.modes[dev_id] = mode
            self._save()
            self._log(dev_id, "mode", mode=mode)
        self._publish_state(dev_id)

    async def switch(self, dev_id, on):
        """Commande manuelle : passe en mode manuel (l'auto ne reprend pas la main)."""
        if self.mode(dev_id) != "manual":
            self.set_mode(dev_id, "manual")
        await self._set(dev_id, bool(on), "app")

    async def snapshot(self):
        out = []
        for dev_id, d in self.registry.devices.items():
            if d.get("kind") != "shelly" or not d.get("ip"):
                continue
            st = self.cache.get(dev_id) or await self.read(dev_id)
            out.append({"id": dev_id, "name": d.get("name"), "ip": d["ip"], "mode": self.mode(dev_id),
                        "online": st.get("online", False), "output": st.get("output"),
                        "power": st.get("power")})
        return out

    # -- boucle automatique ----------------------------------------------
    async def tick(self, now=None):
        """Un passage : lit l'etat de chaque Shelly, applique "relais = heures creuses" en mode auto."""
        now = now or time.time()
        tariff = self.get_tariff()
        for dev_id, d in list(self.registry.devices.items()):
            if d.get("kind") != "shelly" or not d.get("ip"):
                continue
            st = await self.read(dev_id)
            self._publish_state(dev_id)
            if self.mode(dev_id) != "auto" or not st.get("online") or not tariff:
                continue
            want = tariff.is_hc(now)
            if st.get("output") != want:
                try:
                    await self._set(dev_id, want, "auto-hc")
                except ControlError:
                    pass                  # deja journalise ; nouvel essai au prochain passage

    async def run(self, interval=30):
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("erreur de pilotage")
            await asyncio.sleep(interval)
