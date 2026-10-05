#!/usr/bin/env python3
"""登録済み会場の公式サイトを点検し、人が見るべき項目を watch/report.md にまとめる(標準ライブラリのみ)。

- 公式サイト(http/https)だけを読む。SNS(Instagram/X/Facebook等)は読まない。
- robots.txt を守り、1リクエスト/秒以内、識別できるUser-Agentで取得する。
- 自動で venues.json を書き換えない。変更は必ず人が確認して反映する。
使い方: python3 scripts/watch.py [--seeds watch/seeds.txt]
"""
import argparse, hashlib, html, json, re, ssl, sys, time, urllib.request, urllib.robotparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_announce import parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UA = "JamFinderBot/1.0 (+https://github.com/kencomposer5-afk/jam-finder)"
SKIP_HOSTS = ("instagram.com", "x.com", "twitter.com", "facebook.com", "linktr.ee", "example.com", "shimamura.co.jp")
ALWAYS_WORDS = ["閉店", "閉業", "移転", "営業終了"]          # 載っていたら必ず知らせる
DATED_WORDS = ["臨時休業", "休業", "休止", "中止", "休演"]      # 同じ行に日付があるときだけ知らせる
DATE = re.compile(r"\d{1,2}月|\d{1,2}/\d{1,2}|\d{1,2}日|今月|来月|今週")
KEYS = re.compile(r"ジャム|セッション|session|jam", re.I)
JST = timezone(timedelta(hours=9))
_robots = {}


def allowed(url):
    host = urlparse(url)
    base = f"{host.scheme}://{host.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)


def fetch(url):
    """(text, error)。HTMLをテキスト化して返す。"""
    if not allowed(url):
        return "", "robots.txt で取得不可"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        raw = urllib.request.urlopen(req, timeout=15).read(1_000_000)
    except ssl.SSLError as e:
        return "", f"証明書エラー: {e}"
    except Exception as e:
        return "", str(e)[:120]
    finally:
        time.sleep(1)
    for enc in ("utf-8", "shift_jis", "euc-jp"):
        try:
            t = raw.decode(enc)
            break
        except UnicodeDecodeError:
            t = None
    t = t if t is not None else raw.decode("utf-8", "ignore")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", "\n", t)
    return re.sub(r"\n\s*\n+", "\n", html.unescape(t)), ""


def snippets(text, limit=12):
    out, seen = [], set()
    for line in re.split(r"[\n。]", text):
        line = line.strip()
        if 4 <= len(line) <= 200 and KEYS.search(line) and line not in seen:
            seen.add(line)
            out.append(line)
    return out[:limit]


def key(rule):
    w = rule.get("weeks", "every")
    return (rule["weekday"], "every" if w == "every" else tuple(sorted(map(str, w))))


def fmt(k):
    wd = "月火水木金土日"[k[0]]
    return f"{'毎週' if k[1] == 'every' else '第' + '・'.join(k[1])}{wd}曜"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=str(ROOT / "watch/seeds.txt"))
    a = ap.parse_args()
    venues = json.loads((ROOT / "data/venues.json").read_text(encoding="utf-8"))["venues"]
    sp = ROOT / "watch/state.json"
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    attention, ok_count, skipped = [], 0, []

    for v in venues:
        url = v.get("url", "")
        if not url or any(h in urlparse(url).netloc for h in SKIP_HOSTS):
            skipped.append(v["name"])
            continue
        st = state.setdefault(v["id"], {"fail": 0, "hash": ""})
        text, err = fetch(url)
        if err:
            st["fail"] += 1
            msg = f"公式サイトを読めません({err})"
            if st["fail"] >= 3:
                msg += f" — {st['fail']}回連続。**閉店・移転の可能性**があるので確認を"
            attention.append((v["name"], url, [msg]))
            continue
        ok_count += 1
        st["fail"] = 0
        notes = []
        for line in (l.strip() for l in re.split(r"[\n。]", text)):
            if not (4 <= len(line) <= 160):
                continue
            hit = [w for w in ALWAYS_WORDS if w in line] or ([w for w in DATED_WORDS if w in line] if DATE.search(line) else [])
            if hit:
                notes.append(f"「{'、'.join(hit)}」の記載: {line[:100]}")
                if len(notes) >= 3:
                    break
        snips = snippets(text)
        h = hashlib.sha1("\n".join(snips).encode()).hexdigest()[:12]
        if st["hash"] and st["hash"] != h:
            notes.append("ジャム/セッションに関する記載が前回から変わっています(日程・料金の変更かも)")
        st["hash"] = h
        found = {key(r) for r in parse("\n".join(snips))["rules"]}
        reg = {key(r) for r in v.get("rules", [])}
        if found and not (found <= reg):
            notes.append("ページ上に未登録の開催パターン(推測): " + "、".join(fmt(k) for k in sorted(found - reg, key=str)))
        if notes:
            attention.append((v["name"], url, notes))

    drafts = []
    sf = Path(a.seeds)
    if sf.exists():
        for line in sf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            url, _, memo = line.partition(" ")
            if any(h in urlparse(url).netloc for h in SKIP_HOSTS):
                drafts.append((url, memo, None, "SNS等は自動で読めません。告知文を貼ってください"))
                continue
            text, err = fetch(url)
            if err:
                drafts.append((url, memo, None, f"読めません({err})"))
                continue
            snips = snippets(text)
            drafts.append((url, memo, parse("\n".join(snips)) if snips else None, "" if snips else "ジャム/セッションの記載が見つかりません"))

    lines = [f"# 週次チェック({now} JST)", "",
             f"- 点検した会場: {ok_count}件 / 読めなかった: {sum(1 for _, _, n in attention if any('読めません' in x for x in n))}件 / 公式URLなし・SNSのため対象外: {len(skipped)}件",
             "- 自動では何も書き換えていません。内容を確認して `data/venues.json` に反映してください。", ""]
    if attention:
        lines.append("## 要確認")
        for name, url, notes in attention:
            lines.append(f"### {name}\n{url}")
            lines += [f"- {n}" for n in notes]
            lines.append("")
    else:
        lines += ["## 要確認", "なし", ""]
    if drafts:
        lines.append("## 候補URLの解析結果(下書き)")
        for url, memo, res, note in drafts:
            lines.append(f"### {memo or url}\n{url}")
            if note:
                lines.append(f"- {note}")
            if res:
                for r in res["rules"]:
                    lines.append(f"- 推測: {fmt(key(r))} " + (r.get('start', '') + ('〜' + r['end'] if r.get('end') else '')))
                if res["fee"]:
                    lines.append(f"- 料金の記載: {res['fee']}")
                lines += [f"- ⚠ {w}" for w in res["warnings"]]
            lines.append("")
    (ROOT / "watch/report.md").write_text("\n".join(lines), encoding="utf-8")
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines))
    (ROOT / "watch/attention_count").write_text(str(len(attention) + len([d for d in drafts])), encoding="utf-8")


if __name__ == "__main__":
    main()
