"""Добор отрывков с целями, сроками и обязательствами в эталон поиска (задача Григория). Без модели.

    python src/select_gold_commitments.py          # 30 отрывков, по одному на компанию, seed 20261112

Зачем: в основной выборке (select_gold_fragments.py) обязательств мало (14 из 358 заявлений),
поэтому поиск обещаний и целей нельзя проверить. Здесь берём по одному связному куску на компанию,
где больше всего признаков цели: «к 2030 году», «цель», «планируется», «намерена», «стремится достичь».

Не трогает основную выборку. Не берёт куски из data/gold_extract/used_chunks.txt и куски, из которых
взяты примеры инструкции (codebook/Инструкция_по_разметке_v*.md).
Нумерация отрывков продолжает основную: f101, f102, …  Часть выборки: «цели и сроки».
12 отрывков отложенные (для проверки поиска Георгия), 18 рабочие.

Пишет:
  data/gold_extract/fragments_commit.csv, sentences_commit.jsonl
  batches/gold_extract_A/gold_extract_c01..c03.jsonl, batches/gold_extract_B/… (перемешаны)
  дописывает новые куски в data/gold_extract/used_chunks.txt
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from select_gold_fragments import (FIRST_WAVE, ROOT, is_prose, read_chunks, read_reports,  # noqa: E402
                                   split_sentences)

SEED = 20261112
N_HELDOUT = 12
BATCH = 10
TARGET = [
    re.compile(r"\b(к|до)\s+20[2-6]\d\s*(г\.|год)", re.I),
    re.compile(r"\bцел(ь|и|ей|евые|евых|евой)\b", re.I),
    re.compile(r"\bпланиру(ет|ем|ется|ются)|\bплан(ах|ы)\b|запланирован", re.I),
    re.compile(r"\bнамерен|\bобязу(ется|емся)|\bстреми(тся|мся) (к )?достиж", re.I),
    re.compile(r"\b(снизить|сократить|достичь|увеличить|довести)\b", re.I),
]


def target_score(text: str) -> int:
    return sum(len(p.findall(text)) for p in TARGET)


def codebook_quotes() -> list[str]:
    out = []
    for f in (ROOT / "codebook").glob("Инструкция_по_разметке_v*.md"):
        for q in re.findall(r"«([^«»]{40,}?)»", f.read_text(encoding="utf-8")):
            q = q.replace("…", "").strip()
            if len(q) >= 40:
                out.append(re.sub(r"\s+", " ", q[:40]))
    return out


def main() -> None:
    rng = random.Random(SEED)
    used_path = ROOT / "data/gold_extract/used_chunks.txt"
    used = set(used_path.read_text(encoding="utf-8").split())
    quotes = codebook_quotes()
    reports = read_reports()
    companies = FIRST_WAVE + sorted(c for c in reports if c not in FIRST_WAVE)

    picked = []
    for c in companies:
        pool = []
        for r in reports[c]:
            for ch in read_chunks(r["report_id"]):
                t = re.sub(r"\s+", " ", ch["text"])
                if ch["chunk_id"] in used or not is_prose(ch["text"]) or any(q in t for q in quotes):
                    continue
                s = target_score(ch["text"])
                if s >= 3 and re.search(r"20[2-6]\d", ch["text"]):
                    pool.append((s, ch))
        if not pool:
            print("нет подходящих кусков:", c)
            continue
        pool.sort(key=lambda x: (-x[0], x[1]["chunk_id"]))
        best = pool[: 5]  # из пяти лучших берём случайный, чтобы не всегда самый «плотный»
        s, ch = rng.choice(best)
        picked.append({**ch, "company_id": c, "score": s})

    order = list(range(len(picked)))
    rng.shuffle(order)
    heldout = set(order[:N_HELDOUT])

    out = ROOT / "data/gold_extract"
    sentences = []
    with open(out / "fragments_commit.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fragment_id", "chunk_id", "company_id", "report_id", "page", "split", "pilot",
                    "sample_part", "target_block", "score_target", "n_sentences"])
        for i, fr in enumerate(picked):
            fid = f"{fr['report_id']}_f{101 + i:03d}"
            sents = split_sentences(fr["text"])
            split = "отложенный" if i in heldout else "рабочий"
            for j, s in enumerate(sents):
                sentences.append({
                    "sentence_id": f"{fid}_s{j + 1:02d}", "fragment_id": fid, "company_id": fr["company_id"],
                    "report_id": fr["report_id"], "page": fr["page"], "split": split, "pilot": False,
                    "sample_part": "цели и сроки", "sentence": s,
                    "context": " ".join(sents[max(0, j - 1): j + 2]),
                })
            w.writerow([fid, fr["chunk_id"], fr["company_id"], fr["report_id"], fr["page"], split, "",
                        "цели и сроки", "", fr["score"], len(sents)])
    with open(out / "sentences_commit.jsonl", "w", encoding="utf-8") as f:
        for s in sentences:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(used_path, "a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(fr["chunk_id"] for fr in picked))

    fids = [f"{fr['report_id']}_f{101 + i:03d}" for i, fr in enumerate(picked)]
    for k, s in enumerate(range(0, len(fids), BATCH)):
        ids = set(fids[s: s + BATCH])
        name = f"c{k + 1:02d}"
        for who in ("A", "B"):
            rows = [x for x in sentences if x["fragment_id"] in ids]
            if who == "B":
                random.Random(f"{SEED}-{name}").shuffle(rows)
            with open(ROOT / "batches" / f"gold_extract_{who}" / f"gold_extract_{name}.jsonl", "w",
                      encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps({k2: r[k2] for k2 in ("sentence_id", "report_id", "page", "sentence", "context")},
                                       ensure_ascii=False) + "\n")
        print(name, len([x for x in sentences if x["fragment_id"] in ids]), "предложений")

    print("Отрывков:", len(picked), "предложений:", len(sentences), "отложенных:", len(heldout))
    print("По годам:", dict(Counter(fr["report_id"].split("-")[1] for fr in picked)))


if __name__ == "__main__":
    main()
