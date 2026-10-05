#!/usr/bin/env python3
"""告知文(Instagram/X/公式のコピペ)から開催ルールの『下書き』を作る。

  python3 parse_announce.py < announce.txt
出力は必ず人が原文と見比べて確認してから venues.json に入れること(正規表現による推測)。
"""
import json, re, sys

WD = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
KANJI_N = {"第1": 1, "第2": 2, "第3": 3, "第4": 4, "第5": 5, "第一": 1, "第二": 2, "第三": 3, "第四": 4, "第五": 5}


def norm(t: str) -> str:
    t = t.translate(str.maketrans("０１２３４５６７８９：～〜", "0123456789:~~"))
    return t


def parse(text: str):
    t = norm(text)
    out = {"rules": [], "fee": "", "warnings": []}
    # 例: 第2・4水曜 / 毎週木曜 / 最終土曜
    for m in re.finditer(r"(毎週|最終|第[1-5一二三四五](?:[・,、と]第?[1-5一二三四五])*)\s*([月火水木金土日])曜", t):
        head, wd = m.group(1), WD[m.group(2)]
        if head == "毎週":
            weeks = "every"
        elif head == "最終":
            weeks = ["last"]
        else:
            nums = re.findall(r"[1-5一二三四五]", head)
            weeks = [int("一二三四五".index(n) + 1) if n in "一二三四五" else int(n) for n in nums]
        seg = t[m.end(): m.end() + 60]
        tpat = r"(\d{1,2}:\d{2})\s*(?:~|-|–)?\s*(\d{1,2}:\d{2})?"
        tm = re.search(r"(?:START|スタート|開演)\s*" + tpat, seg, re.I) or re.search(tpat, seg)
        rule = {"weekday": wd, "weeks": weeks}
        if tm:
            rule["start"] = tm.group(1)
            if tm.group(2):
                rule["end"] = tm.group(2)
        else:
            out["warnings"].append(f"{m.group(0)}: 時間を読み取れませんでした")
        out["rules"].append(rule)
    for m in re.finditer(r"(?:参加費|チャージ|charge|ミュージックチャージ)[:：\s]*([^\n。]{1,40})", t, re.I):
        out["fee"] = m.group(1).strip()
        break
    if not out["rules"]:
        out["warnings"].append("曜日の記載(毎週○曜/第○○曜/最終○曜)が見つかりません。不定期開催の可能性")
    return out


if __name__ == "__main__":
    print(json.dumps(parse(sys.stdin.read()), ensure_ascii=False, indent=2))
