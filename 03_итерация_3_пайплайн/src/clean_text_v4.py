"""Тексты отчётов, версия v4. Без модели и без PDF. Старые версии не меняет.

    python -I src/clean_text_v4.py

Вход:  data/pages/*.jsonl (v2, как есть)
       data/text_v4/база_MAGN-2025-ИО.jsonl  ММК 2025 с исправленным шрифтом (от src/pdf_evidence_v4.py)
       data/text_v4/переносы.csv             каждый перенос слова и решение по самому PDF
       data/reports/MVDK-2023-ГО.txt, MVDK-2025-ГО.txt (границы страниц — как в v3)
Выход: data/pages_v4/<report_id>.jsonl  тексты по страницам (тот же формат, что v2 и v3)
       data/pages_v4/quality.csv        качество текста
       data/text_v4/колонтитулы.csv     убранные повторяющиеся строки (то же правило, что в v3)

Чем v4 отличается от v3 (исправлено по независимой проверке 16.11.2026):
- дефис ставится ТОЛЬКО на месте переноса и только если так слово написано в самом PDF внутри
  строки (или, если такого слова в PDF нет, по правилу — довод записан в переносы.csv).
  v3 расставлял дефисы по всему тексту по словарю, поэтому «рискориентированный» из PDF
  превращался в «риск-ориентированный»;
- склеены слова, разорванные мягким переносом («действу ющий» → «действующий», 15 тыс. мест):
  v2 и v3 оставляли в них разрыв строки;
- ММК 2025: шрифт исправлен по таблице самого шрифта, а не заменой значков: «№» больше не
  превращается в 9, латиница не сдвигается («GRI», «V», «X», «III–IV»), пробелы на местах;
- «энерго- и ресурсосбережение» остаётся с висячим дефисом (v2 склеивал в «энергои»).
Колонтитулы и границы страниц Мосводоканала — как в v3.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from parse import normalize  # noqa: E402
from clean_text_v3 import (TXT_REPORTS, header_lines, quality, split_pages_txt,  # noqa: E402
                           strip_headers, write_csv)

SRC = ROOT / "data" / "pages"
DST = ROOT / "data" / "pages_v4"
REP = ROOT / "data" / "text_v4"
FONT_FIXED = {"MAGN-2025-ИО"}
KNOWN_BAD = {"TRMK-2023-ИО": "часть шрифта Roboto без таблицы знаков: заголовки и часть страниц — набор значков"}


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def base_pages(rid: str) -> list[dict]:
    """Текст, к которому относятся позиции в переносы.csv: v2, а для ММК 2025 и Мосводоканала — их база."""
    if rid in FONT_FIXED:
        return load(REP / f"база_{rid}.jsonl")
    if rid in TXT_REPORTS:
        txt = (ROOT / "data" / "reports" / f"{rid}.txt").read_text(encoding="utf-8")
        return [{"report_id": rid, "page": p, "text": normalize(t), "n_chars": len(normalize(t).strip())}
                for p, t in split_pages_txt(txt)]
    return load(SRC / f"{rid}.jsonl")


def apply_breaks(text: str, rows: list[dict], where: str) -> str:
    # сначала все места сверяются с исходным текстом (слово может разрываться дважды:
    # «промышленно-|техно-|логический»), потом правки идут с конца, чтобы позиции не съезжали
    for r in rows:
        pos, span = int(r["позиция"]), int(r["длина"])
        left, right = r["слева"], r["справа"]
        if text[pos - len(left):pos] != left or text[pos + span:pos + span + len(right)] != right:
            raise SystemExit(f"{where}: перенос «{left}|{right}» не на своём месте ({pos}) — "
                             "переносы.csv не от этого текста")
    for r in sorted(rows, key=lambda r: -int(r["позиция"])):
        pos, span = int(r["позиция"]), int(r["длина"])
        hy = r["дефис"] or "-"
        dec = r["решение"]
        if dec == "слитно":
            mid = ""
        elif dec == "через дефис":
            mid = hy
        elif dec == "висячий дефис":
            mid = hy + " "
        elif dec == "перенос строки":
            mid = hy + "\n"
        else:
            raise SystemExit(f"{where}: неизвестное решение {dec}")
        text = text[:pos] + mid + text[pos + span:]
    return text


def main() -> None:
    if DST.exists() and any(DST.glob("*.jsonl")):
        sys.exit(f"{DST} уже заполнена: v4 не перезаписываем. Для новой версии сделайте pages_v5.")
    if (REP / "колонтитулы.csv").exists():
        sys.exit("data/text_v4/колонтитулы.csv уже есть: не перезаписываем.")
    breaks = defaultdict(list)
    with open(REP / "переносы.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            breaks[(r["report_id"], int(r["page"]))].append(r)
    DST.mkdir(parents=True, exist_ok=True)
    rids = sorted(p.stem for p in SRC.glob("*.jsonl"))
    heads_out, qrows = [], []
    used = 0
    stat = Counter()
    for rid in rids:
        rows = base_pages(rid)
        heads = header_lines([r["text"] for r in rows])
        for l, c in sorted(heads.items(), key=lambda t: (-t[1], t[0])):
            heads_out.append({"report_id": rid, "строка": l, "страниц": c, "всего_страниц": len(rows)})
        out = []
        hyph = 0
        for r in rows:
            br = breaks.get((rid, int(r["page"])), [])
            used += len(br)
            t = apply_breaks(r["text"], br, f"{rid} стр. {r['page']}")
            stat.update(b["решение"] for b in br)
            hyph += sum(1 for b in br if b["решение"] in ("через дефис", "висячий дефис"))
            t = strip_headers(t, heads)
            out.append({"report_id": rid, "page": r["page"], "text": t, "n_chars": len(t.strip())})
        q = quality(rid, out, hyph)
        q["glued_hyphen_words"] = hyph   # здесь: сколько дефисов оставлено на месте переноса по PDF
        notes = [q["note"]] if q["note"] else []
        if rid in TXT_REPORTS:
            notes.append("из .txt без PDF: page = печатный номер страницы")
            q["verdict"] = "проверить"
        if rid in FONT_FIXED:
            notes.append("шрифт исправлен по таблице шрифта (data/text_v4/шрифт_MAGN-2025_таблица.csv)")
        if rid in KNOWN_BAD:
            notes.append(KNOWN_BAD[rid])
            q["verdict"] = "проверить"
        q["note"] = "; ".join(notes)
        qrows.append(q)
        with open(DST / f"{rid}.jsonl", "x", encoding="utf-8", newline="\n") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{rid}: {len(out)} стр., колонтитулов {len(heads)}, дефисов на месте переноса {hyph}", flush=True)
    total = sum(len(v) for v in breaks.values())
    if used != total:
        raise SystemExit(f"использовано переносов {used} из {total}: страницы не совпали")
    write_csv(DST / "quality.csv", qrows)
    write_csv(REP / "колонтитулы.csv", heads_out, ["report_id", "строка", "страниц", "всего_страниц"])
    print("переносы:", dict(stat), "| качество:", Counter(q["verdict"] for q in qrows))


if __name__ == "__main__":
    main()
