"""Сведение разметок A и B эталона поиска, каппа Коэна, итоговый gold_extract.csv. Без модели.

    python src/agreement_extract.py --version v1 [--only-pilot]

Читает:
  data/gold_extract/sentences.jsonl
  llm/gold_extract_A/<версия>/*.json, llm/gold_extract_B/<версия>/*.json   (ответы разметчиков)
  llm/gold_extract_C/<версия>/*.json          (третий проход по расхождениям, если есть)
  data/gold_extract/resolutions.csv           (решения Егора Д.: sentence_id;field;value;note), если есть
Пишет:
  data/out/gold_extract.csv                   по шаблону templates/gold_extract_шаблон.csv
  data/gold_extract/disagreements.csv         что разошлось и что решено
  data/gold_extract/agreement.md              каппа и доли совпадений по полям
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["is_claim", "type", "second_type", "esg_block", "topic", "has_number", "has_deadline", "flag"]
TYPES = {"обязательство", "результат", "декларация"}


def load_answers(who: str, version: str) -> dict[str, dict]:
    out = {}
    for f in sorted((ROOT / "llm" / f"gold_extract_{who}" / version).glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, dict):  # ответ в обёртке с метаданными: {"model": ..., "items": [...]}
            data = data.get("items", [])
        for r in data:
            r = {k: (str(v).strip() if v is not None else "") for k, v in r.items()}
            if r.get("is_claim") == "нет":
                for k in FIELDS[1:]:
                    r[k] = ""
            out[r["sentence_id"]] = r
    return out


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return None if pe == 1 else (po - pe) / (1 - pe)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    ap.add_argument("--only-pilot", action="store_true")
    args = ap.parse_args()

    sents = []  # основная выборка + добор «цели и сроки» (sentences_commit.jsonl), если есть
    for name in ("sentences.jsonl", "sentences_commit.jsonl"):
        p = ROOT / "data/gold_extract" / name
        if p.exists():
            sents += [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    if args.only_pilot:
        sents = [s for s in sents if s["pilot"]]
    A, B, C = (load_answers(w, args.version) for w in ("A", "B", "C"))
    res = {}
    rp = ROOT / "data/gold_extract/resolutions.csv"
    if rp.exists():
        for r in csv.DictReader(open(rp, encoding="utf-8-sig"), delimiter=";"):
            res[(r["sentence_id"], r["field"])] = (r["value"], r.get("note", ""))

    missing = [s["sentence_id"] for s in sents if s["sentence_id"] not in A or s["sentence_id"] not in B]
    sents_ok = [s for s in sents if s["sentence_id"] in A and s["sentence_id"] in B]

    # каппа: is_claim по всем; остальное — где оба сказали «да»
    lines = [f"# Согласие разметчиков A и B ({args.version}{', только пробные' if args.only_pilot else ''})", "",
             f"Предложений: {len(sents)}, размечено обоими: {len(sents_ok)}, без ответа: {len(missing)}", "",
             "| Поле | На чём считаем | n | Совпало | Каппа Коэна |", "|---|---|---|---|---|"]
    both = [s for s in sents_ok if A[s["sentence_id"]].get("is_claim") == "да" == B[s["sentence_id"]].get("is_claim")]
    for f in ["is_claim", "type", "esg_block", "topic", "has_number", "has_deadline"]:
        base = sents_ok if f == "is_claim" else both
        a = [A[s["sentence_id"]].get(f, "") for s in base]
        b = [B[s["sentence_id"]].get(f, "") for s in base]
        k = kappa(a, b)
        agree = sum(x == y for x, y in zip(a, b)) / len(a) if a else 0
        lines.append(f"| {f} | {'все предложения' if f == 'is_claim' else 'оба: заявление'} | {len(a)} | "
                     f"{agree:.0%} | {'—' if k is None else f'{k:.2f}'} |")
    ta = Counter(A[s["sentence_id"]]["type"] for s in both)
    lines += ["", "Распределение типов у A на общих заявлениях: " + ", ".join(f"{k} {v}" for k, v in ta.most_common())]
    # по частям выборки: каппа is_claim и типа отдельно, чтобы высокое согласие на лёгких кусках не прятало трудные
    lines += ["", "## По частям выборки", "", "| Часть | Предложений | is_claim: совпало / каппа | Тип: n / совпало / каппа |",
              "|---|---|---|---|"]
    for part in sorted({s.get("sample_part", "") for s in sents_ok}):
        ps = [s for s in sents_ok if s.get("sample_part", "") == part]
        pb = [s for s in ps if s in both]
        a1 = [A[s["sentence_id"]].get("is_claim", "") for s in ps]; b1 = [B[s["sentence_id"]].get("is_claim", "") for s in ps]
        a2 = [A[s["sentence_id"]].get("type", "") for s in pb]; b2 = [B[s["sentence_id"]].get("type", "") for s in pb]
        k1, k2 = kappa(a1, b1), kappa(a2, b2)
        ag1 = sum(x == y for x, y in zip(a1, b1)) / max(len(a1), 1)
        ag2 = sum(x == y for x, y in zip(a2, b2)) / max(len(a2), 1)
        lines.append(f"| {part} | {len(ps)} | {ag1:.0%} / {'—' if k1 is None else f'{k1:.2f}'} | "
                     f"{len(pb)} / {ag2:.0%} / {'—' if k2 is None else f'{k2:.2f}'} |")
    # матрица типов A×B (включая «нет» = не заявление)
    lab = ["нет", "обязательство", "результат", "декларация"]
    def t_of(r):
        return r.get("type", "") if r.get("is_claim") == "да" else "нет"
    m = Counter((t_of(A[s["sentence_id"]]), t_of(B[s["sentence_id"]])) for s in sents_ok)
    lines += ["", "## Матрица: строки A, столбцы B", "", "| A \\ B | " + " | ".join(lab) + " |", "|---" * (len(lab) + 1) + "|"]
    for x in lab:
        lines.append(f"| {x} | " + " | ".join(str(m[(x, y)]) for y in lab) + " |")
    (ROOT / "data/gold_extract/agreement.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # итог: совпало → берём; разошлось → решение человека, иначе большинство A/B/C, иначе «на проверку»
    tmpl = open(ROOT / "templates/gold_extract_шаблон.csv", encoding="utf-8-sig").readline().strip().split(";")
    out_rows, dis_rows = [], []
    for s in sents_ok:
        sid = s["sentence_id"]
        a, b, c = A[sid], B[sid], C.get(sid, {})
        row = {"sentence_id": sid, "fragment_id": s["fragment_id"], "company_id": s["company_id"],
               "report_id": s["report_id"], "year": s["report_id"].split("-")[1], "page": s["page"],
               "split": s["split"], "sample_part": s.get("sample_part", ""), "sentence": s["sentence"]}
        all_agree, who, notes = True, set(), []
        for f in FIELDS:
            row[f"A_{f}"], row[f"B_{f}"] = a.get(f, ""), b.get(f, "")
            if (sid, f) in res:
                val, note = res[(sid, f)]
                who.add("Егор Д.")
                notes.append(note)
            elif a.get(f, "") == b.get(f, ""):
                val = a.get(f, "")
            elif c and c.get(f, "") in (a.get(f, ""), b.get(f, "")):
                val = c.get(f, "")
                who.add("третий проход")
            else:
                val = "НА ПРОВЕРКУ"
            if a.get(f, "") != b.get(f, ""):
                all_agree = False
                dis_rows.append({"sentence_id": sid, "field": f, "A": a.get(f, ""), "B": b.get(f, ""),
                                 "C": c.get(f, ""), "final": val, "sentence": s["sentence"]})
            row[f"final_{f}"] = val
        row["agree"] = "да" if all_agree else "нет"
        row["resolved_by"] = "совпало" if all_agree else ", ".join(sorted(who)) or "не решено"
        row["resolution_note"] = "; ".join(n for n in notes if n)
        row["human_check"] = ""
        out_rows.append(row)

    (ROOT / "data/out").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/out/gold_extract.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=tmpl, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    with open(ROOT / "data/gold_extract/disagreements.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sentence_id", "field", "A", "B", "C", "final", "sentence"], delimiter=";")
        w.writeheader()
        w.writerows(dis_rows)
    print("\n".join(lines))
    print(f"Расхождений по полям: {len(dis_rows)}, осталось «НА ПРОВЕРКУ»: "
          f"{sum(r['final'] == 'НА ПРОВЕРКУ' for r in dis_rows)}")


if __name__ == "__main__":
    main()
