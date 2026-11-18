"""Перенос заявлений Георгия и эталона поиска на тексты v4. Без модели. Старые файлы не меняет.

    python -I src/migrate_to_v4.py

Вход:  data/out/claims.csv, data/out/gold_extract.csv (исходные, на тексте v2),
       data/out/claims_text_v3.csv, gold_extract_text_v3.csv (для сравнения с v3),
       data/pages_v4/, data/chunks_v4/, data/text_v4/колонтитулы.csv
Выход: data/out/claims_text_v4.csv, data/out/gold_extract_text_v4.csv, data/text_v4/перенос_итог.md

Как ищется цитата. Метки не меняются, модель не вызывается. Для каждой цитаты v2 берутся только
буквы и цифры (без пробелов, дефисов и знаков) и ищутся так же на странице v4. Найденный кусок
страницы v4 и становится новой цитатой — значит, она стоит на странице дословно, а буквы те же,
что в v2. Для ММК 2025 знаки цитаты v2 сначала расшифровываются по таблице шрифта
(data/text_v4/шрифт_MAGN-2025_таблица.csv), а цифры и латиница при сверке не учитываются: в v2 они
были искажены («№» → 9, «VR» → «YR»). Если не нашлась —
цитата без строки колонтитула (её v4 убирает), потом соседние страницы (Мосводоканал).
Колонки: text_v2 / sentence_v2, page_v2, text_v3 / sentence_v3 (как было в v3), text_change,
что_изменилось (короткая разница v2 → v4), check_v4; у заявлений ещё chunk_id_v4.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "data" / "out"
REP = ROOT / "data" / "text_v4"
FONT_FIXED = {"MAGN-2025-ИО"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def loose_map(s: str, font: bool = False) -> tuple[str, list[int]]:
    """Только буквы и цифры. font=True (ММК 2025): цифры не берутся, любая латинская буква — «#»:
    в v2 там «№» читался как 9, а латиница была сдвинута, поэтому по ним сверять нельзя."""
    keep, idx = [], []
    for i, ch in enumerate(s):
        if ch.isalnum():
            c = ch.lower().replace("ё", "е")
            if font:
                if c.isdigit():
                    continue
                if "a" <= c <= "z":
                    c = "#"
            keep.append(c)
            idx.append(i)
    return "".join(keep), idx


def loose(s: str, font: bool = False) -> str:
    return loose_map(s, font)[0]


def font_table() -> dict[str, str]:
    """ММК 2025: знак в v2 (номер рисунка шрифта) → буква, по таблице, которую строит pdf_evidence_v4.py."""
    t = {}
    for r in read(REP / "шрифт_MAGN-2025_таблица.csv"):
        ch = chr(int(r["номер_рисунка"]))
        if not ("a" <= ch.lower() <= "z" or ch.isdigit() or ch in " \n"):
            t[ch] = r["знак"]
    return t


FONT = None


def decode_font(q: str) -> str:
    global FONT
    if FONT is None:
        FONT = font_table()
    return "".join(FONT.get(ch, ch) for ch in q)


def read(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write(p: Path, rows: list[dict], fields: list[str]) -> None:
    with open(p, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)


class Pages:
    def __init__(self):
        self.text: dict[tuple[str, int], str] = {}
        self.lmap: dict[tuple[str, int], tuple[str, list[int]]] = {}
        for f in (ROOT / "data/pages_v4").glob("*.jsonl"):
            for r in map(json.loads, open(f, encoding="utf-8")):
                t = norm(r["text"])
                self.text[(f.stem, int(r["page"]))] = t
                self.lmap[(f.stem, int(r["page"]))] = loose_map(t, f.stem in FONT_FIXED)

    def find(self, rid: str, page: int, quote: str) -> str | None:
        """Кусок страницы v4 с теми же буквами, что у цитаты, дословно как на странице."""
        if (rid, page) not in self.text:
            return None
        lq = loose(quote, rid in FONT_FIXED)
        if not lq:
            return None
        lp, idx = self.lmap[(rid, page)]
        k = lp.find(lq)
        if k < 0:
            return None
        t = self.text[(rid, page)]
        a, b = idx[k], idx[k + len(lq) - 1] + 1
        q = norm(quote)
        # знаки по краям цитаты («…», точка в конце) — если на странице они стоят так же
        # для ММК 2025 цифры в ключ не входят — их по краям цитаты добираем так же, как знаки
        edge = r"[\W\d_]*" if rid in FONT_FIXED else r"[^\w]*"
        lead = re.match("^" + edge, q).group(0)
        trail = re.search(edge + "$", q).group(0)
        if lead and t[max(0, a - len(lead)):a] == lead:
            a -= len(lead)
        if trail and t[b:b + len(trail)] == trail:
            b += len(trail)
        return t[a:b].strip()


def diff_note(old: str, new: str) -> str:
    a, b = norm(old).split(" "), norm(new).split(" ")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            out.append(f"«{' '.join(a[i1:i2])}» → «{' '.join(b[j1:j2])}»")
    s = "; ".join(out)
    return s if len(s) <= 300 else s[:297] + "…"


def migrate(rows, idcol, textcol, pages: Pages, heads, v3rows, chunks=None):
    v3 = {r[idcol]: r for r in v3rows}
    res, stat, checks = [], Counter(), Counter()
    for r in rows:
        rid, page = r["report_id"], int(r["page"])
        q2 = r[textcol]
        q = norm(decode_font(q2)) if rid in FONT_FIXED else q2
        new = dict(r)
        new[f"{textcol}_v2"] = q2
        new["page_v2"] = r["page"]
        new[f"{textcol}_v3"] = v3.get(r[idcol], {}).get(textcol, "")
        status, found, pg = "проверить", None, page
        hit = pages.find(rid, page, q)
        if hit is not None:
            found = hit
            status = "без изменений" if norm(hit) == norm(q2) else "исправлен текст"
        else:
            fnt = rid in FONT_FIXED
            lq = loose(q, fnt)
            inside = [h for h in heads.get(rid, []) if loose(h, fnt) and loose(h, fnt) in lq]
            if inside and lq.replace("".join(loose(h, fnt) for h in inside), "") == "":
                status = "колонтитул целиком"
            if inside and status != "колонтитул целиком":
                q_no = q
                for h in sorted(inside, key=len, reverse=True):
                    q_no = norm(q_no.replace(h, " "))
                lq_no = lq
                for h in sorted(inside, key=lambda h: -len(loose(h, fnt))):
                    lq_no = lq_no.replace(loose(h, fnt), "")
                hit = pages.find(rid, page, q_no) or (pages.find(rid, page, lq_no) if lq_no else None)
                if hit:
                    found, status = hit, "колонтитул внутри"
            if found is None and status != "колонтитул целиком":
                for d in (1, -1, 2, -2, 3, -3):
                    hit = pages.find(rid, page + d, q)
                    if hit:
                        found, pg, status = hit, page + d, "другая страница"
                        break
        if found is not None:
            new[textcol] = found
            new["page"] = str(pg)
        new["text_change"] = status
        new["что_изменилось"] = diff_note(q2, found) if found is not None and status != "без изменений" else ""
        ok = found is not None and norm(found) in pages.text.get((rid, pg), "")
        new["check_v4"] = "есть на странице v4" if ok else "проверить"
        if chunks is not None:
            t = norm(new[textcol])
            hits = [cid for cid, ct in chunks.get((rid, int(new["page"])), []) if t in ct]
            new["chunk_id_v4"] = hits[0] if hits else ""
            checks["кусок v4 найден" if hits else "кусок v4 не найден (цитата на стыке кусков)"] += 1
        stat[status] += 1
        checks[new["check_v4"]] += 1
        res.append(new)
    return res, stat, checks


def main() -> None:
    for name in ("claims_text_v4.csv", "gold_extract_text_v4.csv"):
        if (OUT / name).exists():
            sys.exit(f"{name} уже есть, не перезаписываю")
    pages = Pages()
    heads = defaultdict(list)
    for r in read(REP / "колонтитулы.csv"):
        heads[r["report_id"]].append(r["строка"])
    chunks = defaultdict(list)
    for f in (ROOT / "data/chunks_v4").glob("*.jsonl"):
        for r in map(json.loads, open(f, encoding="utf-8")):
            chunks[(r["report_id"], int(r["page"]))].append((r["chunk_id"], norm(r["text"])))

    lines = ["# Перенос заявлений и эталона на тексты v4", "",
             "Метки не менялись, модель не вызывалась; поправлены только текст цитаты и страница.",
             "Цитата v4 — кусок страницы v4 с теми же буквами и цифрами, что у цитаты v2.", ""]
    claims = read(OUT / "claims.csv")
    res, stat, checks = migrate(claims, "claim_id", "text", pages, heads, read(OUT / "claims_text_v3.csv"), chunks)
    fields = list(claims[0].keys()) + ["chunk_id_v4", "text_v2", "page_v2", "text_v3", "text_change",
                                       "что_изменилось", "check_v4"]
    write(OUT / "claims_text_v4.csv", res, fields)
    v3diff = sum(1 for r in res if r["text_v3"] and norm(r["text_v3"]) != norm(r["text"]))
    lines += ["## claims_text_v4.csv", "", f"Строк: {len(res)}; цитата отличается от v3: {v3diff}", ""]
    lines += [f"- {k}: {v}" for k, v in stat.most_common()] + [""]
    lines += [f"- {k}: {v}" for k, v in checks.most_common()] + [""]
    lines += [f"  - {r['claim_id']} ({r['report_id']}, стр. {r['page']}): {r['text_change']}"
              for r in res if r["check_v4"] != "есть на странице v4"] + [""]

    gold = read(OUT / "gold_extract.csv")
    res, stat, checks = migrate(gold, "sentence_id", "sentence", pages, heads, read(OUT / "gold_extract_text_v3.csv"))
    fields = list(gold[0].keys()) + ["sentence_v2", "page_v2", "sentence_v3", "text_change", "что_изменилось",
                                     "check_v4"]
    write(OUT / "gold_extract_text_v4.csv", res, fields)
    v3diff = sum(1 for r in res if r["sentence_v3"] and norm(r["sentence_v3"]) != norm(r["sentence"]))
    lines += ["## gold_extract_text_v4.csv", "", f"Строк: {len(res)}; предложение отличается от v3: {v3diff}", ""]
    lines += [f"- {k}: {v}" for k, v in stat.most_common()] + [""]
    lines += [f"- {k}: {v}" for k, v in checks.most_common()] + [""]
    lines += [f"  - {r['sentence_id']} ({r['report_id']}, стр. {r['page']}, заявление: {r['final_is_claim']}): "
              f"{r['text_change']} — «{r['sentence'][:120]}»" for r in res if r["check_v4"] != "есть на странице v4"]
    with open(REP / "перенос_итог.md", "x", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
