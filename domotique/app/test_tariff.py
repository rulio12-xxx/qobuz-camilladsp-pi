import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from tariff import Tariff

TZ = ZoneInfo("Europe/Paris")
CFG = {"timezone": "Europe/Paris", "hp_eur_kwh": 0.20, "hc_eur_kwh": 0.10,
       "base_eur_kwh": 0.18, "export_eur_kwh": 0.12, "hc_ranges": [["22:30", "06:30"]]}


def ts(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=TZ).timestamp()


class T(unittest.TestCase):
    def setUp(self):
        self.t = Tariff(CFG)

    def test_is_hc_across_midnight(self):
        for h, mi, hc in [(22, 29, False), (22, 30, True), (23, 59, True), (0, 0, True),
                          (6, 29, True), (6, 30, False), (12, 0, False)]:
            self.assertEqual(self.t.is_hc(ts(2026, 11, 15, h, mi)), hc, (h, mi))

    def test_now_and_next_switch(self):
        n = self.t.now(ts(2026, 11, 15, 12))
        self.assertEqual((n["period"], n["next_period"]), ("HP", "HC"))
        self.assertEqual(n["next_switch"], ts(2026, 11, 15, 22, 30))
        n = self.t.now(ts(2026, 11, 15, 23))
        self.assertEqual((n["period"], n["next_switch"]), ("HC", ts(2026, 11, 16, 6, 30)))

    def test_split_crossing_boundary(self):
        # 22:00 -> 23:00, 2 kWh : moitie HP (22:00-22:30), moitie HC
        hp, hc = self.t.split(ts(2026, 11, 15, 22), ts(2026, 11, 15, 23), 2.0)
        self.assertAlmostEqual(hp, 1.0)
        self.assertAlmostEqual(hc, 1.0)

    def test_split_long_interval_two_boundaries(self):
        # 06:00 -> 23:00 : HC 06:00-06:30 (0.5h), HP 06:30-22:30 (16h), HC 22:30-23:00 (0.5h)
        hp, hc = self.t.split(ts(2026, 11, 15, 6), ts(2026, 11, 15, 23), 17.0)
        self.assertAlmostEqual(hp, 16.0)
        self.assertAlmostEqual(hc, 1.0)

    def test_report_savings(self):
        r = self.t.report([(ts(2026, 11, 15, 23), ts(2026, 11, 16, 1), 10.0),    # HC
                           (ts(2026, 11, 15, 12), ts(2026, 11, 15, 13), 5.0)],   # HP
                          export_kwh=3.0)
        self.assertAlmostEqual(r["cost_eur"], 10 * 0.10 + 5 * 0.20)
        self.assertAlmostEqual(r["savings_vs_all_hp_eur"], 15 * 0.20 - 2.0)
        self.assertAlmostEqual(r["savings_vs_base_eur"], 15 * 0.18 - 2.0)
        self.assertAlmostEqual(r["hc_ratio"], 10 / 15, places=3)
        self.assertAlmostEqual(r["export_revenue_eur"], 0.36)

    def test_dst_day_is_ok(self):
        # passage a l'heure d'hiver 2026-10-25 : l'intervalle 22:00 -> 07:00 dure 10 h reelles
        hp, hc = self.t.split(ts(2026, 10, 24, 22), ts(2026, 10, 25, 7), 10.0)
        self.assertAlmostEqual(hp + hc, 10.0)


if __name__ == "__main__":
    unittest.main()
