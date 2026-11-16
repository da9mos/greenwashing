"""Какие заявления и предложения эталона задевает чистка текста v3. Без модели. Ничего не правит.

    python src/affected_v3.py

Вход:  data/out/claims.csv, data/out/gold_extract.csv, data/pages/ (v2), data/pages_v3/,
       data/text_v3/замены_дефис.csv, data/text_v3/колонтитулы.csv
Выход: data/text_v3/затронутые_заявления.csv, data/text_v3/затронутый_эталон.csv, итог в консоль.

Статусы:
- «без изменений»          цитата дословно есть на той же странице v3;
- «исправлен текст»        после тех же замен (шрифт ММК 2025, дефис) цитата есть на странице v3,
                           новый текст в колонке text_v3;
- «колонтитул целиком»     всё предложение — строка колонтитула (в v3 убрана);
- «колонтитул внутри»      в цитату вклеена строка колонтитула или меню, которую v3 убирает;
                           text_v3 — цитата без неё (если она так находится на странице);
- «другая страница»        цитата нашлась на соседней странице (Мосводоканал: границы страниц уточнены);
- «не найдено»             нужна перепроверка.
Ответы моделей в llm/ и таблицы в data/out/ не меняются: это список для следующей версии.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clean_text_v3 import BROKEN_FONT_REPORTS, fix_font  # noqa: E402

REP = ROOT / "data" / "text_v3"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def pages(folder: str) -> dict[str, dict[int, str]]:
    out = {}
    for f in (ROOT / "data" / folder).glob("*.jsonl"):
        d = {}
        with open(f, encoding="utf-8") as fh:
            for l in fh:
                r = json.loads(l)
                d[int(r["page"])] = norm(r["text"])
        out[f.stem] = d
    return out


def read_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main() -> None:
    v3 = pages("pages_v3")
    hmap = {r["было"]: r["стало"] for r in read_csv(REP / "замены_дефис.csv")}
    heads = defaultdict(list)
    for r in read_csv(REP / "колонтитулы.csv"):
        heads[r["report_id"]].append(norm(r["строка"]))

    def hyph(t: str) -> str:
        return re.sub(r"(?<![-А-Яа-яЁё])[А-Яа-яЁё]+(?![-А-Яа-яЁё])",
                      lambda m: (lambda w, n: m.group(0)[:n.index("-")] + "-" + m.group(0)[n.index("-"):] if n else w)
                      (m.group(0), hmap.get(m.group(0).lower())), t)

    def check(rid: str, page: int, text: str) -> tuple[str, str, str, str]:
        rep = v3.get(rid, {})
        t = norm(text)
        if t in rep.get(page, ""):
            return "без изменений", "", str(page), ""
        why = []
        t2 = t
        if rid in BROKEN_FONT_REPORTS:
            t2 = norm(fix_font(t2))
            if t2 != t:
                why.append("шрифт")
        # перенос с пробелом («окру- жающей»): пробуем склеить и без дефиса, и с дефисом — берём то, что есть на странице
        page_text = rep.get(page, "")
        def join(m, keep):
            return f"{m.group(1)}-{m.group(2)}" if keep else m.group(1) + m.group(2)
        brk = re.compile(r"([А-Яа-яЁё]+)[-\u2010\u2011\u00ad] ([а-яё]+)")
        if brk.search(t2):
            cand = brk.sub(lambda m: join(m, False), t2)
            if cand not in page_text and hyph(cand) not in page_text:
                cand = brk.sub(lambda m: join(m, True), t2)
            if cand != t2:
                t2 = cand
                why.append("перенос")
        t3 = hyph(t2)
        if t3 != t2:
            why.append("дефис")
        if why and t3 in rep.get(page, ""):
            return "исправлен текст", t3, str(page), ", ".join(why)
        if any(t3 in h for h in heads.get(rid, [])):
            return "колонтитул целиком", "", "", "предложение — это строка колонтитула, в v3 её нет"
        hit = sorted(h for h in heads.get(rid, []) if h and h in t3)
        if hit:
            t4 = t3
            for h in sorted(hit, key=lambda x: (-len(x), x)):
                t4 = norm(t4.replace(h, " "))
            found = t4 in rep.get(page, "")
            return "колонтитул внутри", t4 if found else "", str(page), "убрано: " + " | ".join(hit)
        for d in (1, -1, 2, -2, 3, -3):
            if t3 in rep.get(page + d, ""):
                return "другая страница", t3 if t3 != t else "", str(page + d), ", ".join(why)
        return "не найдено", "", "", ", ".join(why)

    for src, idcol, textcol, out_name in [
        (ROOT / "data/out/claims.csv", "claim_id", "text", "затронутые_заявления.csv"),
        (ROOT / "data/out/gold_extract.csv", "sentence_id", "sentence", "затронутый_эталон.csv"),
    ]:
        rows = read_csv(src)
        res, stat = [], Counter()
        for r in rows:
            status, new, page3, note = check(r["report_id"], int(r["page"]), r[textcol])
            stat[status] += 1
            if status != "без изменений":
                extra = {"final_is_claim": r.get("final_is_claim", "")} if "final_is_claim" in r else {}
                res.append({idcol: r[idcol], "report_id": r["report_id"], "page_v2": r["page"], "page_v3": page3,
                            "статус": status, "что": note, "text_v2": r[textcol], "text_v3": new, **extra})
        fields = [idcol, "report_id", "page_v2", "page_v3", "статус", "что", "text_v2", "text_v3"]
        if "final_is_claim" in rows[0]:
            fields.append("final_is_claim")
        with open(REP / out_name, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            w.writeheader()
            w.writerows(res)
        print(src.name, len(rows), dict(stat))


if __name__ == "__main__":
    main()
