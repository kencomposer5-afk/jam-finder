#!/usr/bin/env python3
"""venues.json の開催ルールを展開して data/sessions.json を生成する(標準ライブラリのみ)。

- 毎日実行すると、常に「今日から HORIZON_DAYS 日先まで」が自動で埋まる。
- overrides で臨時休業/臨時開催を上書き。
- 会場URLを軽く確認し、休業・中止の告知キーワードがあれば警告フラグを付ける(任意)。
"""
import json, re, sys, urllib.request, calendar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HORIZON_DAYS = 90
JST = timezone(timedelta(hours=9))
WARN_WORDS = ["臨時休業", "休止", "中止", "お休み", "休演"]


def nth_weekday(d: date) -> int:
    return (d.day - 1) // 7 + 1


def is_last(d: date) -> bool:
    return d.day + 7 > calendar.monthrange(d.year, d.month)[1]


def matches(rule, d: date) -> bool:
    if d.weekday() != rule["weekday"]:
        return False
    weeks = rule.get("weeks", "every")
    if weeks == "every":
        return True
    return nth_weekday(d) in weeks or ("last" in weeks and is_last(d))


def check_page(url: str) -> bool:
    """告知ページに休業系キーワードがあれば True。取得失敗は False(警告しない)。"""
    if not url or "example.com" in url:
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jam-session-app/1.0"})
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        return any(w in re.sub(r"<[^>]+>", " ", html) for w in WARN_WORDS)
    except Exception as e:
        print(f"skip {url}: {e}", file=sys.stderr)
        return False


def main():
    cfg = json.loads((ROOT / "data/venues.json").read_text(encoding="utf-8"))
    today = datetime.now(JST).date()
    overrides = {(o["venue"], o["date"]): o for o in cfg.get("overrides", [])}
    sessions = []
    for v in cfg["venues"]:
        warn = check_page(v.get("url"))
        for i in range(HORIZON_DAYS + 1):
            d = today + timedelta(days=i)
            for rule in v["rules"]:
                if not matches(rule, d):
                    continue
                ov = overrides.get((v["id"], d.isoformat()), {})
                if ov.get("cancel"):
                    continue
                sessions.append({
                    "id": f'{v["id"]}-{d.isoformat()}-{rule["start"] or "x"}',
                    "date": d.isoformat(),
                    "start": ov.get("start", rule["start"]), "time_note": rule.get("time_note", ""),
                    "end": ov.get("end", rule.get("end", "")),
                    "venue": v["name"], "pref": v.get("pref", ""), "area": v["area"],
                    "genre": rule.get("genre", v["genre"]),
                    "address": v.get("address", ""), "url": v.get("url", ""),
                    "fee": rule.get("fee", v.get("fee", "")), "level": v.get("level", ""),
                    "instruments": rule.get("instruments", v.get("instruments", "")),
                    "note": ov.get("note", ""),
                    "warn": warn, "sample": bool(v.get("sample")),
                })
    for o in cfg.get("overrides", []):  # 臨時開催(extra)
        if o.get("extra") and o["date"] >= today.isoformat():
            v = next(x for x in cfg["venues"] if x["id"] == o["venue"])
            sessions.append({**o["extra"], "id": f'{v["id"]}-{o["date"]}-x', "date": o["date"],
                             "venue": v["name"], "pref": v.get("pref", ""), "area": v["area"], "url": v.get("url", ""),
                             "warn": False, "sample": bool(v.get("sample"))})
    sessions.sort(key=lambda s: (s["date"], s["start"] or "12:00"))
    out = {"updated": datetime.now(JST).isoformat(timespec="minutes"), "sessions": sessions}
    (ROOT / "data/sessions.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(sessions)} sessions written")


if __name__ == "__main__":
    main()
