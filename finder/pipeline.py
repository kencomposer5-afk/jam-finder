#!/usr/bin/env python3
"""首都圏ジャズセッション自動収集 MVP(標準ライブラリのみ)。

  python3 finder/pipeline.py all        # plan → seed → search → crawl → report
  python3 finder/pipeline.py plan|seed|search|crawl|report

APIキー(任意。無ければその工程はスキップされ、網羅率に『未実施』と出る):
  GOOGLE_CSE_KEY + GOOGLE_CSE_CX   Google カスタム検索(ウェブ検索)
  GOOGLE_PLACES_KEY                Google Places(店の一覧・Place ID)
  ANTHROPIC_API_KEY                AI判定(無ければルールベース判定)
安全設計: robots.txt順守・1秒間隔・取得ページ数上限・SNSは読まない(URL発見のみ)。
"""
import argparse, json, os, re, sqlite3, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import watch  # noqa: E402  (fetch / robots / snippets を再利用)
from parse_announce import parse  # noqa: E402

JST = timezone(timedelta(hours=9))
DB = HERE / "finder.db"
OUT = HERE / "out"
SOCIAL = ("instagram.com", "facebook.com", "x.com", "twitter.com", "tiktok.com")
WEIGHT = {"official": 40, "social": 5, "places": 15, "peatix": 15, "atjazz": 10, "web": 10}
WD = "月火水木金土日"


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS queries(id INTEGER PRIMARY KEY, pref TEXT, area TEXT, kind TEXT, medium TEXT, q TEXT UNIQUE, prio INTEGER, status TEXT DEFAULT 'pending', n INTEGER DEFAULT 0, done_at TEXT);
    CREATE TABLE IF NOT EXISTS pages(url TEXT PRIMARY KEY, medium TEXT, via TEXT, name TEXT, status TEXT DEFAULT 'pending', fail INTEGER DEFAULT 0, fetched_at TEXT, hash TEXT);
    CREATE TABLE IF NOT EXISTS candidates(key TEXT PRIMARY KEY, name TEXT, pref TEXT, city TEXT, station TEXT, address TEXT, url TEXT, place_id TEXT, lat REAL, lng REAL, phone TEXT,
      is_session INTEGER, ai_conf REAL, frequency TEXT, start_time TEXT, price TEXT, beginner TEXT, guitar TEXT, amp TEXT, real_book TEXT, host TEXT, genre TEXT,
      sources TEXT, score INTEGER, state TEXT, first_seen TEXT, last_verified TEXT, snippet TEXT);
    """)
    return c


def now():
    return datetime.now(JST).strftime("%Y-%m-%d")


def cfg():
    return json.loads((HERE / "regions.json").read_text(encoding="utf-8"))


# ---------------- plan ----------------
def plan(a):
    c, k = db(), cfg()
    n = 0
    for pref, r in k["regions"].items():
        if a.pref and a.pref not in pref:
            continue
        areas = [("station", s, i) for i, s in enumerate(r["stations"])] + [("city", s, i) for i, s in enumerate(r["cities"])]
        for kind, area, i in areas:
            for kw in k["keywords"]:
                n += c.execute("INSERT OR IGNORE INTO queries(pref,area,kind,medium,q,prio) VALUES(?,?,?,?,?,?)", (pref, area, kind, "web", kw.format(a=area), i)).rowcount
            if kind == "city":
                for t in k["place_types"]:
                    n += c.execute("INSERT OR IGNORE INTO queries(pref,area,kind,medium,q,prio) VALUES(?,?,?,?,?,?)", (pref, area, kind, "places", f"{area} {t}", i)).rowcount
    c.commit()
    print(f"plan: 新規クエリ {n}件(合計 {c.execute('select count(*) from queries').fetchone()[0]}件)")


# ---------------- providers ----------------
def http_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers={"User-Agent": watch.UA, "Content-Type": "application/json", **(headers or {})})
    return json.load(urllib.request.urlopen(req, timeout=20))


def cse(q, key, cx):
    j = http_json("https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode({"key": key, "cx": cx, "q": q, "num": 10, "lr": "lang_ja"}))
    return [(i["link"], i.get("title", "")) for i in j.get("items", [])]


def places(q, key):
    j = http_json("https://places.googleapis.com/v1/places:searchText", {"textQuery": q, "languageCode": "ja", "regionCode": "JP"},
                  {"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri,places.location,places.nationalPhoneNumber"})
    return j.get("places", [])


def host_medium(url):
    h = urllib.parse.urlparse(url).netloc
    if any(s in h for s in SOCIAL):
        return "social"
    if "peatix.com" in h:
        return "peatix"
    if "jazz.co.jp" in h:
        return "atjazz"
    return "web"


def search(a):
    c = db()
    ck, cx, pk = os.getenv("GOOGLE_CSE_KEY"), os.getenv("GOOGLE_CSE_CX"), os.getenv("GOOGLE_PLACES_KEY")
    if not (ck and cx) and not pk:
        print("search: APIキー未設定のためスキップ(GOOGLE_CSE_KEY+GOOGLE_CSE_CX / GOOGLE_PLACES_KEY)。公式サイト巡回のみ実行します")
        return
    done = 0
    for row in c.execute("SELECT * FROM queries WHERE status='pending' ORDER BY prio, id").fetchall():
        if done >= a.max_queries:
            break
        medium = row["medium"]
        if (medium == "web" and not (ck and cx)) or (medium == "places" and not pk):
            continue
        try:
            if medium == "web":
                hits = cse(row["q"], ck, cx)
                for url, title in hits:
                    c.execute("INSERT OR IGNORE INTO pages(url,medium,via,name) VALUES(?,?,?,?)", (url, host_medium(url), "cse", title))
                n = len(hits)
            else:
                ps = places(row["q"], pk)
                for p in ps:
                    nm = p.get("displayName", {}).get("text", "")
                    loc = p.get("location", {})
                    key = "place:" + p["id"]
                    c.execute("INSERT OR IGNORE INTO candidates(key,name,pref,address,url,place_id,lat,lng,phone,sources,state,first_seen,score,is_session) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                              (key, nm, row["pref"], p.get("formattedAddress", ""), p.get("websiteUri", ""), p["id"], loc.get("latitude"), loc.get("longitude"), p.get("nationalPhoneNumber", ""), "places", "NEW", now(), WEIGHT["places"]))
                    if p.get("websiteUri"):
                        c.execute("INSERT OR IGNORE INTO pages(url,medium,via,name) VALUES(?,?,?,?)", (p["websiteUri"], host_medium(p["websiteUri"]), "places", nm))
                    c.execute("INSERT OR IGNORE INTO queries(pref,area,kind,medium,q,prio) VALUES(?,?,?,?,?,?)", (row["pref"], row["area"], "venue", "web", f'"{nm}" ジャムセッション', 999))
                n = len(ps)
            c.execute("UPDATE queries SET status='done', n=?, done_at=? WHERE id=?", (n, now(), row["id"]))
            done += 1
            time.sleep(0.5)
        except Exception as e:  # クォータ超過等は止める
            print("search: 中断", str(e)[:120])
            break
        c.commit()
    c.commit()
    print(f"search: {done}クエリ実行")


def seed(a):
    c, n = db(), 0
    for v in json.loads((ROOT / "data/venues.json").read_text(encoding="utf-8"))["venues"]:
        if v.get("url"):
            n += c.execute("INSERT OR IGNORE INTO pages(url,medium,via,name) VALUES(?,?,?,?)", (v["url"], "official", "registered", v["name"])).rowcount
    sf = ROOT / "watch/seeds.txt"
    if sf.exists():
        for line in sf.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                u, _, m = line.strip().partition(" ")
                n += c.execute("INSERT OR IGNORE INTO pages(url,medium,via,name) VALUES(?,?,?,?)", (u, host_medium(u) if host_medium(u) == "social" else "official", "seed", m)).rowcount
    c.commit()
    print(f"seed: 新規URL {n}件")


# ---------------- classify ----------------
JAM = re.compile(r"ジャム|セッション|session|jam", re.I)
JOIN = re.compile(r"参加|飛び入り|どなたでも|歓迎|ホスト|リーダー|楽器持参|置き楽器|ミニマム")
LIVE = re.compile(r"ライブ|live|LIVE|出演")
GENRES = {"jazz": r"ジャズ|jazz|ビバップ|スタンダード", "blues": r"ブルース|blues", "funk": r"ファンク|funk|ソウル|soul", "fusion": r"フュージョン|fusion", "bossa": r"ボサ|bossa"}


def flag(t, pat, neg=None):
    return "可" if re.search(pat, t) else "不明"


def classify_rules(text, url):
    sn = watch.snippets(text, 20)
    t = "\n".join(sn)
    p = parse(t)
    jam, join, live = bool(JAM.search(t)), bool(JOIN.search(t)), bool(LIVE.search(t))
    conf = 0.2 + (0.3 if jam else 0) + (0.2 if join else 0) + (0.1 if p["rules"] else 0) - (0.3 if (live and not jam) else 0)
    r = p["rules"][0] if p["rules"] else None
    freq = "、".join(("毎週" if x["weeks"] == "every" else "第" + "・".join(map(str, x["weeks"]))) + WD[x["weekday"]] + "曜" for x in p["rules"][:3]) or "不明"
    host = re.search(r"(?:ホスト|Host|リーダー)\s*[:：]?\s*([^\s、,。／/]{2,20})", t)
    g = [k for k, v in GENRES.items() if re.search(v, text, re.I)]
    return {"is_session": int(conf >= 0.5), "ai_conf": round(max(0, min(1, conf)), 2), "frequency": freq, "start_time": (r or {}).get("start", ""),
            "price": p["fee"], "beginner": "◎" if re.search(r"初心者|ビギナー|初めて|beginner", t, re.I) else "不明",
            "guitar": "可" if re.search(r"ギター.{0,6}(歓迎|可|OK|参加)|(歓迎|可|OK).{0,6}ギター", t) else "不明", "amp": "あり" if re.search(r"アンプ.{0,6}(貸|あり|完備|常設)", t) else "不明",
            "real_book": "使用" if re.search(r"黒本|リアルブック|real ?book", t, re.I) else "不明", "host": host.group(1) if host else "", "genre": "/".join(g), "snippet": " / ".join(sn[:4])[:400]}


def classify_llm(snip, name):
    """ANTHROPIC_API_KEY があれば、ルール判定をAI判定で補強する(未設定なら None)。"""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or not snip:
        return None
    prompt = ("次はライブバー等のウェブページ抜粋です。一般客が演奏参加できるジャズ/ブルースのセッション(ジャム)を開催しているか判定し、JSONだけを返してください。"
              '{"is_session":bool,"confidence":0-1,"frequency":"毎週○曜/第n○曜/不定期/不明","beginner_friendly":"◎/○/△/不明","guitar_allowed":"可/不可/不明"}\n'
              f"店名: {name}\n抜粋:\n{snip[:3000]}")
    try:
        j = http_json("https://api.anthropic.com/v1/messages", {"model": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"), "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]},
                      {"x-api-key": key, "anthropic-version": "2023-06-01"})
        m = re.search(r"\{.*\}", j["content"][0]["text"], re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as e:
        print("AI判定エラー:", str(e)[:100])
        return None


def venue_key(name, url, place_id=""):
    if place_id:
        return "place:" + place_id
    h = urllib.parse.urlparse(url).netloc.replace("www.", "")
    return "url:" + h if h and not any(s in h for s in SOCIAL) else "name:" + re.sub(r"\s+", "", name.lower())


def score(medium_set, text):
    s = sum(WEIGHT.get(m, 0) for m in medium_set)
    y, m = datetime.now(JST).year, datetime.now(JST).month
    s += 20 if re.search(rf"{y}年|{y}/|{m}月", text) else 0
    return min(100, s)


def crawl(a):
    c = db()
    rows = c.execute("SELECT * FROM pages WHERE status IN ('pending','ok') AND (fetched_at IS NULL OR fetched_at < ?) ORDER BY CASE medium WHEN 'official' THEN 0 ELSE 1 END LIMIT ?", (a.refetch_before, a.max_pages)).fetchall()
    n = 0
    for p in rows:
        if p["medium"] == "social":
            c.execute("UPDATE pages SET status='social-skip' WHERE url=?", (p["url"],))
            continue
        text, err = watch.fetch(p["url"])
        if err:
            c.execute("UPDATE pages SET fail=fail+1, status=CASE WHEN fail>=2 THEN 'dead' ELSE status END, fetched_at=? WHERE url=?", (now(), p["url"]))
            if p["fail"] + 1 >= 3:
                c.execute("UPDATE candidates SET state='終了候補' WHERE url=?", (p["url"],))
            continue
        res = classify_rules(text, p["url"])
        ai = classify_llm(res["snippet"], p["name"])
        if ai:
            res["is_session"] = int(bool(ai.get("is_session"))); res["ai_conf"] = float(ai.get("confidence", res["ai_conf"]))
            for k_ai, k in (("beginner_friendly", "beginner"), ("guitar_allowed", "guitar")):
                if ai.get(k_ai) and ai[k_ai] != "不明":
                    res[k] = ai[k_ai]
            if ai.get("frequency") and ai["frequency"] != "不明":
                res["frequency"] = ai["frequency"]
        key = venue_key(p["name"], p["url"])
        old = c.execute("SELECT * FROM candidates WHERE key=?", (key,)).fetchone()
        sources = sorted(set((old["sources"].split(",") if old and old["sources"] else []) + [p["medium"]]))
        sc = score(sources, text)
        state = "NEW" if not old else ("更新" if any(old[k] != res[k] for k in ("frequency", "price", "start_time") if old[k]) else ("要確認" if sc < 50 else "確認済"))
        if not old:
            c.execute("INSERT INTO candidates(key,name,url,first_seen) VALUES(?,?,?,?)", (key, p["name"], p["url"], now()))
        c.execute("""UPDATE candidates SET is_session=?,ai_conf=?,frequency=?,start_time=?,price=?,beginner=?,guitar=?,amp=?,real_book=?,host=?,genre=?,snippet=?,sources=?,score=?,state=?,last_verified=?,url=COALESCE(NULLIF(url,''),?) WHERE key=?""",
                  (res["is_session"], res["ai_conf"], res["frequency"], res["start_time"], res["price"], res["beginner"], res["guitar"], res["amp"], res["real_book"], res["host"], res["genre"], res["snippet"], ",".join(sources), sc, state, now(), p["url"], key))
        c.execute("UPDATE pages SET status='ok', fail=0, fetched_at=? WHERE url=?", (now(), p["url"]))
        n += 1
        c.commit()
    print(f"crawl: {n}ページ処理")


# ---------------- report ----------------
def report(a):
    c, k = db(), cfg()
    OUT.mkdir(exist_ok=True)
    rows = [dict(r) for r in c.execute("SELECT * FROM candidates ORDER BY is_session DESC, score DESC")]
    (OUT / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# 収集レポート({now()})", ""]
    sessions = [r for r in rows if r["is_session"]]
    L.append(f"- 候補 {len(rows)}件 / セッション判定 {len(sessions)}件 / 要確認 {sum(1 for r in rows if r['state'] == '要確認')}件 / 終了候補 {sum(1 for r in rows if r['state'] == '終了候補')}件\n")
    L.append("## 網羅率(regions.json のリストに対する割合)")
    L.append("| 都県 | 市区町村 検索済 | 駅 検索済 | ウェブ検索 | Places |")
    L.append("|---|---|---|---|---|")
    for pref, r in k["regions"].items():
        def cov(kind, med):
            tot = c.execute("SELECT count(distinct area) FROM queries WHERE pref=? AND kind=? AND medium=?", (pref, kind, med)).fetchone()[0]
            dn = c.execute("SELECT count(distinct area) FROM queries WHERE pref=? AND kind=? AND medium=? AND status='done'", (pref, kind, med)).fetchone()[0]
            return dn, tot
        def pct(dn, tot):
            return f"{dn}/{tot}" if tot else "-"
        cw, sw, pl = cov("city", "web"), cov("station", "web"), cov("city", "places")
        qd = c.execute("SELECT count(*) FROM queries WHERE pref=? AND medium='web' AND status='done'", (pref,)).fetchone()[0]
        qt = c.execute("SELECT count(*) FROM queries WHERE pref=? AND medium='web'", (pref,)).fetchone()[0]
        L.append(f"| {pref} | {pct(*cw)} | {pct(*sw)} | {qd}/{qt}クエリ | {pct(*pl)} |")
    pg = c.execute("SELECT medium, count(*) n, sum(status='ok') ok FROM pages GROUP BY medium").fetchall()
    L += ["", "## 取得ページ(媒体別)", "| 媒体 | 件数 | 取得成功 |", "|---|---|---|"] + [f"| {r['medium']} | {r['n']} | {r['ok'] or 0} |" for r in pg]
    L += ["", "※ 検索・Places は APIキー未設定の場合は『0』のままです。", "", "## セッション候補(上位)"]
    for r in sessions[:40]:
        L.append(f"- [{r['state']}] **{r['name']}** score={r['score']} 頻度={r['frequency']} 開始={r['start_time'] or '-'} 料金={r['price'] or '-'} 初心者={r['beginner']} ギター={r['guitar']} ジャンル={r['genre'] or '-'}  {r['url']}")
    (OUT / "report.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "seed", "search", "crawl", "report", "all"])
    ap.add_argument("--pref", default="")
    ap.add_argument("--max-queries", type=int, default=90, help="1回の検索クエリ上限(無料枠は1日100)")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--refetch-before", default=now(), help="この日付より前に取得したページだけ再取得")
    a = ap.parse_args()
    for f in ({"all": [plan, seed, search, crawl, report]}.get(a.cmd) or [{"plan": plan, "seed": seed, "search": search, "crawl": crawl, "report": report}[a.cmd]]):
        f(a)


if __name__ == "__main__":
    main()
