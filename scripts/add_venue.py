#!/usr/bin/env python3
"""venues.json に会場を1件追加し、その場で検証して sessions.json を再生成する。

  python3 add_venue.py --id foo --name "店名" --pref 東京 --area 高円寺 --genre jazz blues \
     --url https://... --fee "1,500円+1ドリンク" --rules '[{"weekday":3,"weeks":"every","start":"19:30"}]'
"""
import argparse, json, re, subprocess, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument("--id", required=True); p.add_argument("--name", required=True)
p.add_argument("--pref", required=True, choices=["東京", "埼玉", "神奈川", "千葉"])
p.add_argument("--area", required=True); p.add_argument("--genre", nargs="+", required=True, choices=["jazz", "blues", "rock", "funk", "pop", "classic", "all"])
p.add_argument("--url", required=True); p.add_argument("--address", default="")
p.add_argument("--fee", default=""); p.add_argument("--level", default=""); p.add_argument("--instruments", default="")
p.add_argument("--rules", required=True, help="JSON配列")
a = p.parse_args()

rules = json.loads(a.rules)
for r in rules:
    assert r["weekday"] in range(7), "weekday は 0(月)〜6(日)"
    assert re.fullmatch(r"\d{1,2}:\d{2}", r.get("start", "")) or r.get("time_note"), "start (HH:MM) か time_note が必要"
    assert r.get("weeks", "every") == "every" or isinstance(r["weeks"], list), "weeks は 'every' か配列"
path = ROOT / "data/venues.json"
cfg = json.loads(path.read_text(encoding="utf-8"))
if any(v["id"] == a.id for v in cfg["venues"]):
    sys.exit(f"id '{a.id}' は既に存在します")
cfg["venues"].append({"id": a.id, "name": a.name, "pref": a.pref, "area": a.area, "genre": a.genre,
                      "address": a.address, "url": a.url, "fee": a.fee, "level": a.level,
                      "instruments": a.instruments, "verified": date.today().isoformat(), "rules": rules})
path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
subprocess.check_call([sys.executable, str(ROOT / "scripts/update.py")])
