"""Отбор отрывков для эталона поиска заявлений (задача Григория).

Без модели и без ключа. Запуск после разбора PDF на куски (data/chunks/<report_id>.jsonl,
строки {"chunk_id","report_id","page","text"}):

    python src/select_gold_fragments.py            # 100 отрывков, seed 20261112
    python src/select_gold_fragments.py --n 60     # другое число

Что делает:
  1. Берёт по каждой компании отчёт самого раннего и самого позднего года (2023 и 2025;
     у SHLZ и SVEZ — 2023 и 2024).
  2. ESG-куски берутся только из связного текста (не таблицы и не указатели GRI/SASB).
     Квота: 10 компаний первой очереди получают 4 отрывка, остальные 3 (итого 100).
     Из них 1 на компанию — случайный кусок отчёта, остальные — ESG-куски с лучшим
     счётом по словарю, блоки E/S/G по кругу (чтобы вышло примерно поровну).
  3. Делит отрывки на предложения с номерами, помечает 40 отложенных и 20 пробных.
  4. Пишет:
       data/gold_extract/fragments.csv     список отрывков (CSV ; UTF-8 BOM)
       data/gold_extract/sentences.jsonl   предложения с контекстом
       batches/gold_extract_A/*.jsonl      партии по 10 отрывков в исходном порядке
       batches/gold_extract_B/*.jsonl      те же предложения, перемешанные
       data/gold_extract/used_chunks.txt   эти куски нельзя брать в примеры инструкции
  и печатает сводку по компаниям, блокам, годам и частям выборки.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_CSV = ROOT.parent / "01_итерация_1_сбор_данных" / "выборка_30" / "reports.csv"
FIRST_WAVE = ["NORN", "MAGN", "CHMF", "LKOH", "TATN", "PHOR", "SIBR", "SGZH", "RVDK", "GAZP"]

LEXICON = {
    "E": ["выброс", "парников", "климат", "углерод", "сброс", "сточн", "водопотреб", "водн", "отход",
          "рекультив", "биоразнообраз", "экологи", "энергоэффектив", "возобновля", "загрязн", "атмосфер"],
    "S": ["травм", "несчаст", "охран труда", "безопасност", "персонал", "сотрудник", "работник",
          "заработн", "обучени", "благотвор", "местн сообществ", "регион", "права человека", "социальн",
          "LTIFR", "здоров"],
    "G": ["совет директоров", "независим", "акционер", "коррупц", "этик", "комплаенс", "аудит",
          "заверени", "управлени рисками", "раскрыти", "поставщик", "закупк", "комитет", "вознагражд"],
}
# не режем после инициалов («А.С. Иванов») и сокращений «г.», «т.», «руб.»
SENT_SPLIT = re.compile(r"(?<![\s.][А-ЯЁA-Z]\.)(?<!\sг\.)(?<!\sт\.)(?<!руб\.)(?<=[.!?…»])\s+(?=[«\"(A-ZА-ЯЁ0-9])")
INDEX_MARKERS = re.compile(r"GRI\s?\d|SASB|UNCTAD|МЭР-\d|СОКБ|Страница в отчете|Указатель|Содержание", re.I)


def is_prose(text: str) -> bool:
    """Связный текст, а не таблица или указатель: мало цифр, есть законченные предложения."""
    digits = sum(ch.isdigit() for ch in text) / max(len(text), 1)
    periods = len(re.findall(r"[а-яё]{3,}[.!?](\s|$)", text))
    return digits < 0.08 and periods >= 3 and len(INDEX_MARKERS.findall(text)) <= 1


def block_scores(text: str) -> dict[str, int]:
    low = text.lower()
    return {b: sum(low.count(w.lower()) for w in words) for b, words in LEXICON.items()}


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = [p.strip() for p in SENT_SPLIT.split(text) if p.strip()]
    merged: list[str] = []
    for p in parts:  # слишком короткие куски (номера, «т.», подписи) клеим к предыдущему
        if merged and len(p) < 25:
            merged[-1] += " " + p
        else:
            merged.append(p)
    return merged


def read_reports() -> dict[str, list[dict]]:
    by_company: dict[str, list[dict]] = defaultdict(list)
    with open(REPORTS_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            by_company[row["company_id"]].append(row)
    return by_company


def read_chunks(report_id: str) -> list[dict]:
    path = ROOT / "data" / "chunks" / f"{report_id}.jsonl"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pick_reports(rows: list[dict]) -> list[str]:
    """Самый ранний и самый поздний год; при нескольких отчётах за год — тот, где больше кусков."""
    by_year: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r["report_id"])
    years = sorted(by_year)
    chosen = []
    for y in ([years[0], years[-1]] if len(years) > 1 else years):
        best = max(by_year[y], key=lambda rid: len(read_chunks(rid)))
        if read_chunks(best):
            chosen.append(best)
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--heldout", type=int, default=40)
    ap.add_argument("--pilot", type=int, default=20)
    ap.add_argument("--batch", type=int, default=10, help="отрывков в партии")
    ap.add_argument("--seed", type=int, default=20261112)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    reports = read_reports()
    all_companies = FIRST_WAVE + sorted(c for c in reports if c not in FIRST_WAVE)
    # компании без разобранных отчётов (например, MVDK, если сайт недоступен) выпадают,
    # их квота делится между остальными
    missing = [c for c in all_companies if not any(read_chunks(r["report_id"]) for r in reports[c])]
    companies = [c for c in all_companies if c not in missing]
    base, extra = divmod(args.n, len(companies))
    quota = {c: base + (1 if i < extra else 0) for i, c in enumerate(companies)}

    fragments = []
    block_cycle = ["E", "S", "G"]
    cycle_pos = 0
    for c in companies:
        rids = pick_reports(reports[c])
        if not rids:
            missing.append(c)
            continue
        pool = []
        for rid in rids:
            for ch in read_chunks(rid):
                sc = block_scores(ch["text"])
                pool.append({**ch, "company_id": c, "scores": sc, "total": sum(sc.values()),
                             "prose": is_prose(ch["text"])})
        used: set[str] = set()
        k = quota[c]
        n_random = max(1, round(k * 0.3))
        for i in range(k - n_random):
            rid = rids[i % len(rids)]  # чередуем ранний и поздний отчёт
            want = block_cycle[cycle_pos % 3]
            cycle_pos += 1
            cands = [p for p in pool if p["report_id"] == rid and p["chunk_id"] not in used and p["prose"]] or \
                    [p for p in pool if p["chunk_id"] not in used and p["prose"]] or \
                    [p for p in pool if p["chunk_id"] not in used]
            best = max(cands, key=lambda p: (p["scores"][want], p["total"], -int(p["page"])))
            used.add(best["chunk_id"])
            fragments.append({**best, "sample_part": "ESG-кусок", "target_block": want})
        top_ids = {p["chunk_id"] for p in sorted(pool, key=lambda p: -p["total"])[:60 * len(rids)]}
        for _ in range(n_random):
            rest = [p for p in pool if p["chunk_id"] not in used and p["chunk_id"] not in top_ids] or \
                   [p for p in pool if p["chunk_id"] not in used]
            pick = rng.choice(rest)
            used.add(pick["chunk_id"])
            fragments.append({**pick, "sample_part": "случайный", "target_block": ""})

    # отложенные: по одному на компанию, остальное добирается случайно; пробные — из рабочих
    order = list(range(len(fragments)))
    rng.shuffle(order)
    heldout, seen = set(), set()
    for i in order:
        if fragments[i]["company_id"] not in seen and len(heldout) < args.heldout:
            heldout.add(i)
            seen.add(fragments[i]["company_id"])
    for i in order:
        if len(heldout) >= args.heldout:
            break
        heldout.add(i)
    working = [i for i in order if i not in heldout]
    pilot = set(working[: args.pilot])

    out = ROOT / "data" / "gold_extract"
    out.mkdir(parents=True, exist_ok=True)
    sentences = []
    with open(out / "fragments.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fragment_id", "chunk_id", "company_id", "report_id", "page", "split",
                    "pilot", "sample_part", "target_block", "score_E", "score_S", "score_G", "n_sentences"])
        for i, fr in enumerate(fragments):
            fid = f"{fr['report_id']}_f{i + 1:03d}"
            sents = split_sentences(fr["text"])
            split = "отложенный" if i in heldout else "рабочий"
            for j, s in enumerate(sents):
                sentences.append({
                    "sentence_id": f"{fid}_s{j + 1:02d}", "fragment_id": fid,
                    "company_id": fr["company_id"], "report_id": fr["report_id"], "page": fr["page"],
                    "split": split, "pilot": i in pilot, "sample_part": fr["sample_part"], "sentence": s,
                    "context": " ".join(sents[max(0, j - 1): j + 2]),
                })
            w.writerow([fid, fr["chunk_id"], fr["company_id"], fr["report_id"], fr["page"], split,
                        "да" if i in pilot else "", fr["sample_part"], fr["target_block"],
                        fr["scores"]["E"], fr["scores"]["S"], fr["scores"]["G"], len(sents)])

    with open(out / "sentences.jsonl", "w", encoding="utf-8") as f:
        for s in sentences:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    (out / "used_chunks.txt").write_text("\n".join(fr["chunk_id"] for fr in fragments), encoding="utf-8")

    # партии: сначала пробная (pilot), затем остальные по args.batch отрывков
    frag_ids = [f"{fr['report_id']}_f{i + 1:03d}" for i, fr in enumerate(fragments)]
    pilot_ids = [frag_ids[i] for i in sorted(pilot)]
    rest_ids = [frag_ids[i] for i in range(len(fragments)) if i not in pilot]
    groups = [("pilot", pilot_ids)] + [
        (f"b{k + 1:02d}", rest_ids[s: s + args.batch]) for k, s in enumerate(range(0, len(rest_ids), args.batch))]
    for who in ("A", "B"):
        d = ROOT / "batches" / f"gold_extract_{who}"
        d.mkdir(parents=True, exist_ok=True)
        for name, ids in groups:
            rows = [s for s in sentences if s["fragment_id"] in set(ids)]
            if who == "B":
                rows = rows[:]
                random.Random(f"{args.seed}-{name}").shuffle(rows)
            with open(d / f"gold_extract_{name}.jsonl", "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps({k: r[k] for k in ("sentence_id", "report_id", "page", "sentence", "context")},
                                       ensure_ascii=False) + "\n")

    print(f"Отрывков: {len(fragments)}, предложений: {len(sentences)}, партий на разметчика: {len(groups)}")
    print("По частям:", dict(Counter(fr["sample_part"] for fr in fragments)))
    print("По целевому блоку:", dict(Counter(fr["target_block"] or "случайный" for fr in fragments)))
    print("По годам:", dict(Counter(fr["report_id"].split("-")[1] for fr in fragments)))
    print("Рабочих / отложенных / пробных:", len(fragments) - len(heldout), len(heldout), len(pilot))
    print("Компаний в выборке:", len({fr["company_id"] for fr in fragments}))
    if missing:
        print("НЕТ КУСКОВ (отчёты не разобраны?):", ", ".join(missing))


if __name__ == "__main__":
    main()
