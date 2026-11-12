"""Список для выборочной проверки эталона Егором Д. Без модели.

    python src/build_review_list.py --version v3

Берёт data/out/gold_extract.csv (после agreement_extract.py) и data/gold_extract/disagreements.csv и пишет
data/gold_extract/для_Егора_проверка.csv:
  - все предложения, где осталось «НА ПРОВЕРКУ»;
  - 12 случайных решений третьего прохода;
  - 15 случайных совпавших предложений из основной выборки;
  - 8 случайных совпавших обязательств из части «цели и сроки» (чтобы проверить новые цели и сроки).
Seed фиксирован, список воспроизводим.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261112
F = ["is_claim", "type", "esg_block", "topic", "has_number", "has_deadline", "flag"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v3")
    v = ap.parse_args().version
    rng = random.Random(SEED)
    gold = list(csv.DictReader(open(ROOT / "data/out/gold_extract.csv", encoding="utf-8-sig"), delimiter=";"))
    dis = list(csv.DictReader(open(ROOT / "data/gold_extract/disagreements.csv", encoding="utf-8-sig"), delimiter=";"))
    by_sid = {}
    for d in dis:
        by_sid.setdefault(d["sentence_id"], []).append(d)
    ctx = {}
    import json
    for name in ("sentences.jsonl", "sentences_commit.jsonl"):
        for l in open(ROOT / "data/gold_extract" / name, encoding="utf-8"):
            if l.strip():
                s = json.loads(l)
                ctx[s["sentence_id"]] = s["context"]

    unresolved = [g for g in gold if any(g[f"final_{f}"] == "НА ПРОВЕРКУ" for f in F)]
    by_c = [g for g in gold if g["resolved_by"] == "третий проход" and g not in unresolved]
    agreed_main = [g for g in gold if g["agree"] == "да" and g["sample_part"] != "цели и сроки"]
    agreed_commit = [g for g in gold if g["agree"] == "да" and g["sample_part"] == "цели и сроки"
                     and g["final_type"] == "обязательство"]
    pick = ([(g, "не решено: модели разошлись") for g in unresolved]
            + [(g, "спор решила третья модель") for g in rng.sample(by_c, min(12, len(by_c)))]
            + [(g, "A и B совпали") for g in rng.sample(agreed_main, min(15, len(agreed_main)))]
            + [(g, "A и B совпали: обязательство из добора «цели и сроки»")
               for g in rng.sample(agreed_commit, min(8, len(agreed_commit)))])

    cols = ["№", "sentence_id", "отчёт", "страница", "что_проверить", "предложение", "контекст", "итог_заявление",
            "итог_тип", "итог_блок", "итог_тема", "итог_число", "итог_срок", "итог_флаг", "спорное_поле", "A", "B",
            "C", "Егор_согласен(да/нет)", "Егор_правильно", "комментарий"]
    with open(ROOT / "data/gold_extract/для_Егора_проверка.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for i, (g, why) in enumerate(pick, 1):
            ds = by_sid.get(g["sentence_id"], [])
            w.writerow([i, g["sentence_id"], g["report_id"], g["page"], why, g["sentence"], ctx.get(g["sentence_id"], "")]
                       + [g[f"final_{f}"] for f in F]
                       + ["; ".join(d["field"] for d in ds), "; ".join(d["A"] for d in ds),
                          "; ".join(d["B"] for d in ds), "; ".join(d["C"] for d in ds), "", "", ""])
    print(f"Строк: {len(pick)} (не решено {len(unresolved)}, решения C {min(12, len(by_c))}, "
          f"совпавшие {min(15, len(agreed_main))}, обязательства {min(8, len(agreed_commit))})")


if __name__ == "__main__":
    main()
