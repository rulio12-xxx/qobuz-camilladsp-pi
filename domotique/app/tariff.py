"""Tarif heures pleines / heures creuses : periode courante, prix, couts, economies.

Les horaires HC et les prix viennent de tariff.json (voir tariff.example.json) ;
aucun prix n'est code en dur. Les instants sont des timestamps epoch (UTC) ;
l'heure locale (fuseau configure) ne sert qu'a decider HP/HC.
"""
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def _hm(s):
    h, m = s.split(":")
    return time(int(h), int(m))


class Tariff:
    def __init__(self, cfg):
        self.tz = ZoneInfo(cfg.get("timezone", "Europe/Paris"))
        self.hp = float(cfg["hp_eur_kwh"])
        self.hc = float(cfg["hc_eur_kwh"])
        self.base = cfg.get("base_eur_kwh")          # prix du tarif Base, pour comparer (optionnel)
        self.export = float(cfg.get("export_eur_kwh") or 0)
        self.subscription = float(cfg.get("subscription_eur_month") or 0)
        self.ranges = [(_hm(a), _hm(b)) for a, b in cfg.get("hc_ranges", [])]

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    # -- periode courante -------------------------------------------------
    def _local(self, ts):
        return datetime.fromtimestamp(ts, self.tz)

    def is_hc(self, ts):
        t = self._local(ts).time()
        for a, b in self.ranges:
            if (a <= t < b) if a <= b else (t >= a or t < b):   # plage a cheval sur minuit
                return True
        return False

    def price(self, ts):
        return self.hc if self.is_hc(ts) else self.hp

    def _boundaries(self, start, end):
        """Timestamps de bascule HP<->HC strictement entre start et end (tries)."""
        d0, d1 = self._local(start).date(), self._local(end).date()
        pts = set()
        d = d0 - timedelta(days=1)
        while d <= d1 + timedelta(days=1):
            for a, b in self.ranges:
                for t in (a, b):
                    ts = datetime.combine(d, t, tzinfo=self.tz).timestamp()
                    if start < ts < end:
                        pts.add(ts)
            d += timedelta(days=1)
        return sorted(pts)

    def next_switch(self, ts):
        """Prochain instant de bascule apres ts (cherche sur 2 jours)."""
        b = self._boundaries(ts, ts + 2 * 86400)
        return b[0] if b else None

    def now(self, ts):
        nxt = self.next_switch(ts)
        return {
            "period": "HC" if self.is_hc(ts) else "HP",
            "eur_kwh": self.price(ts),
            "next_switch": nxt,
            "next_period": ("HP" if self.is_hc(ts) else "HC") if nxt else None,
        }

    # -- couts ------------------------------------------------------------
    def split(self, start, end, kwh):
        """Repartit l'energie d'un intervalle [start,end] entre HP et HC, au prorata du temps."""
        if end <= start:
            return (0.0, kwh) if self.is_hc(start) else (kwh, 0.0)
        cuts = [start] + self._boundaries(start, end) + [end]
        hp = hc = 0.0
        for a, b in zip(cuts, cuts[1:]):
            part = kwh * (b - a) / (end - start)
            if self.is_hc((a + b) / 2):
                hc += part
            else:
                hp += part
        return hp, hc

    def report(self, intervals, export_kwh=0.0):
        """intervals : [(start_ts, end_ts, kwh_importes), ...].

        Economies :
          vs_all_hp   : ce que couterait la meme conso entierement payee au prix HP
                        (gain du decalage vers les heures creuses)
          vs_base     : ecart avec le tarif Base, si base_eur_kwh est renseigne
        """
        hp = hc = 0.0
        for s, e, k in intervals:
            a, b = self.split(s, e, k)
            hp += a
            hc += b
        cost_hp, cost_hc = hp * self.hp, hc * self.hc
        total = cost_hp + cost_hc
        kwh = hp + hc
        out = {
            "kwh_hp": round(hp, 4), "kwh_hc": round(hc, 4), "kwh_total": round(kwh, 4),
            "hc_ratio": round(hc / kwh, 4) if kwh else 0.0,
            "cost_hp_eur": round(cost_hp, 4), "cost_hc_eur": round(cost_hc, 4),
            "cost_eur": round(total, 4),
            "cost_all_hp_eur": round(kwh * self.hp, 4),
            "savings_vs_all_hp_eur": round(kwh * self.hp - total, 4),
            "export_kwh": round(export_kwh, 4),
            "export_revenue_eur": round(export_kwh * self.export, 4),
        }
        if self.base is not None:
            out["cost_base_eur"] = round(kwh * float(self.base), 4)
            out["savings_vs_base_eur"] = round(kwh * float(self.base) - total, 4)
        return out
