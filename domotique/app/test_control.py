import asyncio
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import control
import discovery
from tariff import Tariff

TZ = ZoneInfo("Europe/Paris")
TARIFF = Tariff({"timezone": "Europe/Paris", "hp_eur_kwh": 0.2, "hc_eur_kwh": 0.1,
                 "hc_ranges": [["22:30", "06:30"]]})


def ts(h, m=0):
    return datetime(2026, 11, 16, h, m, tzinfo=TZ).timestamp()


class FakeShelly:
    def __init__(self):
        self.output = False
        self.reachable = True
        self.calls = []

    def status(self, ip, gen=2, channel=0):
        if not self.reachable:
            raise OSError("timeout")
        return {"output": self.output, "power": None}

    def set_output(self, ip, on, gen=2, channel=0):
        if not self.reachable:
            raise OSError("timeout")
        self.calls.append(on)
        self.output = on


class T(unittest.TestCase):
    def setUp(self):
        self.fake = FakeShelly()
        control.shelly = self.fake
        self.reg = discovery.Registry()
        self.reg.upsert("shelly-1", kind="shelly", name="chauffe-eau", ip="10.0.0.5", gen=3)
        self.tariff = TARIFF
        self.pub = []
        self.tmp = tempfile.mkdtemp()
        self.c = control.Controller(self.reg, lambda: self.tariff,
                                    lambda t, p, r: self.pub.append(t), self.tmp)

    def run_(self, coro):
        return asyncio.run(coro)

    def test_default_is_manual_and_never_acts(self):
        self.run_(self.c.tick(ts(23)))            # heures creuses, relais eteint
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.c.mode("shelly-1"), "manual")

    def test_auto_follows_hc(self):
        self.c.set_mode("shelly-1", "auto")
        self.run_(self.c.tick(ts(23)))            # HC -> allume
        self.assertEqual(self.fake.calls, [True])
        self.run_(self.c.tick(ts(23, 30)))        # deja allume : rien
        self.assertEqual(self.fake.calls, [True])
        self.run_(self.c.tick(ts(7)))             # HP -> eteint
        self.assertEqual(self.fake.calls, [True, False])

    def test_auto_refused_without_tariff(self):
        self.tariff = None
        with self.assertRaises(control.ControlError):
            self.c.set_mode("shelly-1", "auto")

    def test_unreachable_does_nothing_and_logs_once(self):
        self.c.set_mode("shelly-1", "auto")
        self.fake.reachable = False
        self.run_(self.c.tick(ts(23)))
        self.run_(self.c.tick(ts(23, 1)))
        self.assertEqual(self.fake.calls, [])
        ev = [e["event"] for e in self.c.tail_log()]
        self.assertEqual(ev.count("injoignable"), 1)
        self.fake.reachable = True
        self.run_(self.c.tick(ts(23, 2)))          # revient : reprend l'auto
        self.assertEqual(self.fake.calls, [True])

    def test_manual_switch_leaves_auto(self):
        self.c.set_mode("shelly-1", "auto")
        self.run_(self.c.switch("shelly-1", False))
        self.assertEqual(self.c.mode("shelly-1"), "manual")
        self.run_(self.c.tick(ts(23)))             # ne doit plus rallumer seul
        self.assertEqual(self.fake.calls, [False])

    def test_mode_persists(self):
        self.c.set_mode("shelly-1", "auto")
        c2 = control.Controller(self.reg, lambda: self.tariff, lambda t, p, r: None, self.tmp)
        self.assertEqual(c2.mode("shelly-1"), "auto")

    def test_unknown_device(self):
        with self.assertRaises(control.ControlError):
            self.c.set_mode("nope", "auto")


if __name__ == "__main__":
    unittest.main()
