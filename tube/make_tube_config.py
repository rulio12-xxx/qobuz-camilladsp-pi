#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genere une config CamillaDSP avec etage lampes (niveau 0-3).
Restructure : branches L/R (sans limiter) + tube global + limiter global.
Usage: make_tube_config.py <src.yml> <dst.yml> <niveau 0-3>"""
import sys, re

LEVELS = {
    1: {"threshold": -18, "factor": 1.3, "clip_limit": -3.0, "makeup_gain": 0.5},
    2: {"threshold": -24, "factor": 1.6, "clip_limit": -1.5, "makeup_gain": 1.0},
    3: {"threshold": -22, "factor": 3.0, "clip_limit": -0.3, "makeup_gain": 2.0},
}

def main():
    src, dst, level = sys.argv[1], sys.argv[2], int(sys.argv[3])
    lines = open(src).read().splitlines()

    pidx = next(i for i, l in enumerate(lines) if l.rstrip() == "pipeline:")
    head = lines[:pidx]

    # retirer une ancienne section processors: du head
    cleaned, i = [], 0
    while i < len(head):
        if head[i].rstrip() == "processors:":
            i += 1
            while i < len(head) and (head[i][:1] == " " or head[i].strip() == ""):
                i += 1
            continue
        cleaned.append(head[i]); i += 1
    head = cleaned

    # parser le pipeline : detecter chaque bloc "- type: Filter"
    body = lines[pidx + 1:]
    branches = []
    i = 0
    while i < len(body):
        if body[i].strip() == "- type: Filter":
            # channels
            ch = ""
            j = i + 1
            while j < len(body) and body[j].strip() != "names:":
                if body[j].strip().startswith("channels:"):
                    ch = body[j].strip()
                j += 1
            # names (lignes '- xxx' apres 'names:')
            names = []
            j += 1
            while j < len(body):
                s = body[j].strip()
                if s.startswith("- ") and not s.startswith("- type:"):
                    nm = s[2:].strip()
                    if nm != "limiter":
                        names.append(nm)
                    j += 1
                else:
                    break
            branches.append((ch, names))
            i = j
        else:
            i += 1

    out = list(head)
    if level != 0:
        p = LEVELS[level]
        out += [
            "processors:", "  tube:", "    type: Compressor",
            "    parameters:", "      channels: 2",
            "      attack: 0.005", "      release: 0.05",
            f"      threshold: {p['threshold']}",
            f"      factor: {p['factor']}",
            f"      makeup_gain: {p['makeup_gain']}",
            f"      clip_limit: {p['clip_limit']}",
            "      soft_clip: true",
        ]
    out.append("pipeline:")
    for ch, names in branches:
        out.append("  - type: Filter")
        out.append("    " + (ch if ch else "channels: [0]"))
        out.append("    names:")
        for nm in names:
            out.append("      - " + nm)
    if level != 0:
        out += ["  - type: Processor", "    name: tube"]
    out += ["  - type: Filter", "    channels: [0, 1]", "    names:", "      - limiter"]

    open(dst, "w").write("\n".join(out) + "\n")
    print(f"OK genere: {dst} (niveau {level})")

if __name__ == "__main__":
    main()
