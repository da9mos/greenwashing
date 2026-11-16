"""Перенос заявлений Георгия и эталона поиска на тексты v3. Без модели. Старые файлы не меняет.

    python src/migrate_to_v3.py

Вход:  data/out/claims.csv, data/out/gold_extract.csv (как были, на тексте v2),
       data/text_v3/затронутые_заявления.csv, затронутый_эталон.csv (от src/affected_v3.py),
       data/pages_v3/, data/chunks_v3/
Выход: data/out/claims_text_v3.csv          заявления с цитатой и страницей по тексту v3
       data/out/gold_extract_text_v3.csv    эталон с предложением и страницей по тексту v3
       data/text_v3/перенос_итог.md          сводка и проверка

Что делается: метки (тип, блок, тема, число, срок, итоговые решения эталона) НЕ меняются, модель
не вызывается. Меняются только текст цитаты и страница там, где чистка v3 их поправила
(шрифт ММК 2025, дефис, колонтитул внутри цитаты, страница Мосводоканала). У заявлений
добавляется chunk_id_v3 — кусок из data/chunks_v3, где цитата стоит дословно.
Добавлены колонки: text_v2 (или sentence_v2), page_v2, text_change, check_v3.
check_v3 = «есть на странице v3» или «проверить» (цитату не удалось перенести дословно).

Почему файлы новые: data/out/claims.csv и gold_extract.csv закреплены хэшами в
runs/extract_v1_*.json (сборка Георгия их проверяет), поэтому они остаются как есть.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "out"
REP = ROOT / "data" / "text_v3"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def read(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write(p: Path, rows: list[dict], fields: list[str]) -> None:
    if p.exists():
        raise SystemExit(f"{p.name} уже есть, не перезаписываю")
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)


def load_pages() -> dict[str, dict[int, str]]:
    out = {}
    for f in (ROOT / "data/pages_v3").glob("*.jsonl"):
        with open(f, encoding="utf-8") as fh:
            out[f.stem] = {int(r["page"]): norm(r["text"]) for r in map(json.loads, fh)}
    return out


def load_chunks() -> dict[tuple[str, int], list[tuple[str, str]]]:
    out: dict[tuple[str, int], list[tuple[str, str]]] = {}
    for f in (ROOT / "data/chunks_v3").glob("*.jsonl"):
        with open(f, encoding="utf-8") as fh:
            for r in map(json.loads, fh):
                out.setdefault((r["report_id"], int(r["page"])), []).append((r["chunk_id"], norm(r["text"])))
    return out


def migrate(rows, aff, idcol, textcol, pages, chunks=None):
    res, stat, checks = [], Counter(), Counter()
    for r in rows:
        a = aff.get(r[idcol])
        new = dict(r)
        new[f"{textcol}_v2"] = r[textcol]
        new["page_v2"] = r["page"]
        change = "без изменений"
        if a:
            change = a["статус"]
            if a["text_v3"]:
                new[textcol] = a["text_v3"]
            if a["page_v3"]:
                new["page"] = a["page_v3"]
        t = norm(new[textcol])
        ok = t in pages.get(r["report_id"], {}).get(int(new["page"]), "")
        new["text_change"] = change
        new["check_v3"] = "есть на странице v3" if ok else "проверить"
        if chunks is not None:
            hits = [cid for cid, ct in chunks.get((r["report_id"], int(new["page"])), []) if t in ct]
            new["chunk_id_v3"] = hits[0] if hits else ""
            checks["кусок v3 найден" if hits else "кусок v3 не найден (цитата на стыке кусков)"] += 1
        stat[change] += 1
        checks[new["check_v3"]] += 1
        res.append(new)
    return res, stat, checks


def main() -> None:
    pages, chunks = load_pages(), load_chunks()
    lines = ["# Перенос заявлений и эталона на тексты v3", "",
             "Метки не менялись, модель не вызывалась; поправлены только текст цитаты и страница.", ""]

    claims = read(OUT / "claims.csv")
    aff = {r["claim_id"]: r for r in read(REP / "затронутые_заявления.csv")}
    res, stat, checks = migrate(claims, aff, "claim_id", "text", pages, chunks)
    fields = list(claims[0].keys()) + ["chunk_id_v3", "text_v2", "page_v2", "text_change", "check_v3"]
    write(OUT / "claims_text_v3.csv", res, fields)
    lines += ["## claims_text_v3.csv", "", f"Строк: {len(res)}", ""]
    lines += [f"- {k}: {v}" for k, v in stat.most_common()] + [""]
    lines += [f"- {k}: {v}" for k, v in checks.most_common()] + [""]
    bad = [r for r in res if r["check_v3"] != "есть на странице v3"]
    lines += [f"  - {r['claim_id']} ({r['report_id']}, стр. {r['page']}): {r['text_change']}" for r in bad] + [""]

    gold = read(OUT / "gold_extract.csv")
    aff = {r["sentence_id"]: r for r in read(REP / "затронутый_эталон.csv")}
    res, stat, checks = migrate(gold, aff, "sentence_id", "sentence", pages)
    fields = list(gold[0].keys()) + ["sentence_v2", "page_v2", "text_change", "check_v3"]
    write(OUT / "gold_extract_text_v3.csv", res, fields)
    lines += ["## gold_extract_text_v3.csv", "", f"Строк: {len(res)}", ""]
    lines += [f"- {k}: {v}" for k, v in stat.most_common()] + [""]
    lines += [f"- {k}: {v}" for k, v in checks.most_common()] + [""]
    bad = [r for r in res if r["check_v3"] != "есть на странице v3"]
    lines += [f"  - {r['sentence_id']} ({r['report_id']}, стр. {r['page']}, заявление: {r['final_is_claim']}): "
              f"{r['text_change']} — «{r['sentence'][:120]}»" for r in bad] + [""]
    (REP / "перенос_итог.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
