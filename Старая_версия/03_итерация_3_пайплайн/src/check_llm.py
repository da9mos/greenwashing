"""Проверка ответов моделей-разметчиков и журнала перед сборкой эталона. Без модели.

    python src/check_llm.py --version v3

1. Сводит журнал: строки из runs/manifest_parts/*.csv (по одному файлу на партию, их пишут потоки
   разметчиков, поэтому параллельная запись ничего не затирает) дописываются в runs/manifest.csv,
   если такого batch_id там ещё нет. Старые строки не меняются.
2. Для каждой партии batches/gold_extract_{A,B}/*.jsonl проверяет файл llm/gold_extract_{A,B}/<версия>/:
   есть ли он, совпадают ли sentence_id один в один, допустимы ли значения полей, пусты ли поля
   у «не заявлений», стоит ли has_deadline только у обязательств, есть ли строка в журнале
   и совпадает ли sha256 входного файла.
Печатает список проблем; код выхода 1, если проблемы есть.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYPES = {"обязательство", "результат", "декларация"}
TOPICS = {"вода", "воздух", "отходы", "климат", "биоразнообразие", "земля", "энергия",
          "безопасность труда", "персонал и оплата", "обучение", "права человека", "местные сообщества",
          "клиенты и качество", "совет директоров и акционеры", "этика и антикоррупция",
          "раскрытие и заверение", "управление рисками", "поставщики", "другое"}
FLAGS = {"", "цель изменена", "условное", "ожидаемый эффект"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def merge_manifest() -> list[dict]:
    man = ROOT / "runs/manifest.csv"
    with open(man, encoding="utf-8-sig", newline="") as f:
        header = f.readline().strip().split(";")
    rows = list(csv.DictReader(open(man, encoding="utf-8-sig"), delimiter=";"))
    have = {r["batch_id"] for r in rows}
    added = []
    for p in sorted((ROOT / "runs/manifest_parts").glob("*.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"):
            if r.get("batch_id") and r["batch_id"] not in have:
                added.append(r)
                have.add(r["batch_id"])
    if added:
        with open(man, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header, delimiter=";", extrasaction="ignore")
            w.writerows(added)
        print(f"В журнал дописано строк: {len(added)}")
    return rows + added


def load(p: Path) -> list[dict]:
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("items", []) if isinstance(data, dict) else data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v3")
    v = ap.parse_args().version
    manifest = merge_manifest()
    problems = []
    for who in ("A", "B"):
        for bf in sorted((ROOT / f"batches/gold_extract_{who}").glob("gold_extract_*.jsonl")):
            name = bf.stem
            want = [json.loads(l)["sentence_id"] for l in open(bf, encoding="utf-8") if l.strip()]
            lf = ROOT / f"llm/gold_extract_{who}/{v}/{name}.json"
            if not lf.exists():
                problems.append(f"{who} {name}: нет файла ответа")
                continue
            try:
                got = load(lf)
            except Exception as e:  # битый JSON
                problems.append(f"{who} {name}: не читается ({e})")
                continue
            ids = [r.get("sentence_id") for r in got]
            if set(ids) != set(want) or len(ids) != len(want):
                problems.append(f"{who} {name}: id не совпадают (нет {len(set(want) - set(ids))}, "
                                f"лишних {len(set(ids) - set(want))}, повторов {len(ids) - len(set(ids))})")
            for r in got:
                g = {k: ("" if r.get(k) is None else str(r.get(k)).strip()) for k in
                     ("is_claim", "type", "second_type", "esg_block", "topic", "has_number", "has_deadline", "flag")}
                sid = r.get("sentence_id")
                bad = []
                if g["is_claim"] not in ("да", "нет"):
                    bad.append(f"is_claim={g['is_claim']}")
                elif g["is_claim"] == "нет":
                    if any(g[k] for k in ("type", "second_type", "esg_block", "topic", "has_number", "has_deadline", "flag")):
                        bad.append("у «не заявления» заполнены поля")
                else:
                    if g["type"] not in TYPES: bad.append(f"type={g['type']}")
                    if g["second_type"] and g["second_type"] not in TYPES: bad.append(f"second_type={g['second_type']}")
                    if g["esg_block"] not in ("E", "S", "G"): bad.append(f"esg_block={g['esg_block']}")
                    if g["topic"] not in TOPICS: bad.append(f"topic={g['topic']}")
                    if g["has_number"] not in ("да", "нет"): bad.append(f"has_number={g['has_number']}")
                    if g["type"] == "обязательство" and g["has_deadline"] not in ("да", "нет"):
                        bad.append("у обязательства пустой has_deadline")
                    if g["type"] != "обязательство" and g["has_deadline"]:
                        bad.append("has_deadline не у обязательства")
                    if g["flag"] not in FLAGS: bad.append(f"flag={g['flag']}")
                if bad:
                    problems.append(f"{who} {name} {sid}: " + "; ".join(bad))
            rows = [m for m in manifest if m.get("stage") == f"gold_extract_{who}" and v in m.get("batch_id", "")
                    and name.replace("gold_extract_", "") in m.get("batch_id", "")]
            if not rows:
                problems.append(f"{who} {name}: нет строки в журнале")
            elif not any(m.get("input_sha256") == sha(bf) for m in rows):
                problems.append(f"{who} {name}: sha256 входа в журнале не совпадает с файлом партии")
    print("\n".join(problems) if problems else f"Проблем нет ({v}).")
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
