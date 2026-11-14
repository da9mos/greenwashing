"""Полная проверка эталона поиска заявлений data/out/gold_extract.csv. Без модели.

    python src/audit_gold.py

Проверяет:
  1. Дословность: каждое предложение есть в тексте отчёта (data/pages) на указанной странице.
  2. Поля итоговой разметки: заполнены у заявлений, пусты у «не заявлений», допустимые значения,
     has_deadline только у обязательств, тема из своего блока (раздел 4 инструкции), нет «НА ПРОВЕРКУ».
  3. Подсказки к возможным ошибкам (не обязательно ошибки, смотреть глазами):
     has_number=да без чисел и наоборот; has_deadline=да без года или даты; обязательство без признаков
     будущего; результат с явным будущим («планирует», «к 2030 году»).
  4. Выборка: отрывок целиком в одной части (рабочий / отложенный), нет повторов предложений,
     нет примеров из инструкции в эталоне, покрытие компаний.
Пишет data/gold_extract/audit.md и data/gold_extract/audit_flags.csv (подсказки по пункту 3).
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK_TOPICS = {
    "E": {"вода", "воздух", "отходы", "климат", "биоразнообразие", "земля", "энергия"},
    "S": {"безопасность труда", "персонал и оплата", "обучение", "права человека", "местные сообщества",
          "клиенты и качество"},
    "G": {"совет директоров и акционеры", "этика и антикоррупция", "раскрытие и заверение", "управление рисками",
          "поставщики"},
}
TYPES = {"обязательство", "результат", "декларация"}
FLAGS = {"", "цель изменена", "условное", "ожидаемый эффект"}
NUM_WORDS = re.compile(r"\b(од(ин|на|но)|дв(а|е|ух|умя)|тр(и|ех|ёх)|четыр\w*|пят\w*|шест\w*|сем\w*|восьм\w*|"
                       r"девят\w*|десят\w*|двадцат\w*|сот\w*|тысяч\w*|миллион\w*|миллиард\w*|"
                       r"вдвое|втрое|половин\w*|треть\w*|четверт\w*|десятк\w*|дюжин\w*)\b", re.I)
YEAR = re.compile(r"\b(19|20)\d\d\b")
DATE = re.compile(r"\b(к|до|в|по)\s+(20\d\d|концу|середине|началу|\d{1,2}\s+\w+\s+20\d\d)|\b20\d\d\s*(г|год)|"
                  r"\b(ежегодно|до конца года|в следующем году|в ближайш\w+ (год|лет))", re.I)
FUTURE = re.compile(r"\b(план\w*|намер\w*|будет|будут|будем|станет|продолжит|продолжим|обязу\w*|цел\w*|"
                    r"стрем\w*|предполага\w*|предстоит|ожида\w*|к\s+20\d\d|до\s+20\d\d|перспектив\w*|"
                    r"задач\w*|запланир\w*|направлен\w*|ориентир\w*|прогноз\w*|\w+ит(ь|ся)\b)", re.I)
FUT_STRONG = re.compile(r"\b(планиру\w*|намерен\w*|будет|будут|будем|к\s+20[3-6]\d\s*(г|год))", re.I)


def norm(s: str) -> str:
    s = s.replace("­", "").replace("ё", "е").replace("Ё", "Е")
    s = re.sub(r"-\s+", "", s)
    return re.sub(r"[^0-9a-zа-я%]+", "", s.lower())


def digits_wo_years(s: str) -> list[str]:
    s2 = YEAR.sub(" ", s)
    s2 = re.sub(r"\b(GRI|SASB|ЦУР|SDG|ISO|ГОСТ|ОТЧЕТ|№)\s*[\w.-]*", " ", s2, flags=re.I)
    return re.findall(r"\d+(?:[.,]\d+)?", s2)


def main() -> None:
    gold = list(csv.DictReader(open(ROOT / "data/out/gold_extract.csv", encoding="utf-8-sig"), delimiter=";"))
    pages: dict[tuple[str, int], str] = {}
    for rid in {g["report_id"] for g in gold}:
        for l in open(ROOT / "data/pages" / f"{rid}.jsonl", encoding="utf-8"):
            p = json.loads(l)
            pages[(rid, int(p["page"]))] = norm(p["text"])
    errors, flags = [], []

    # 1. дословность
    for g in gold:
        s = norm(g["sentence"])
        pg = int(g["page"])
        if s in pages.get((g["report_id"], pg), ""):
            continue
        near = "".join(pages.get((g["report_id"], q), "") for q in (pg - 1, pg, pg + 1))
        if s in near:
            continue  # предложение переходит через границу страницы
        if s[:60] in pages.get((g["report_id"], pg), "") or s[-60:] in pages.get((g["report_id"], pg), ""):
            continue  # совпали начало или конец: склейка колонок, проверено частично
        errors.append(f"{g['sentence_id']}: текст не найден на с. {pg} отчёта {g['report_id']}")

    # 2. поля
    for g in gold:
        sid = g["sentence_id"]
        f = {k[6:]: g[k] for k in g if k.startswith("final_")}
        if "НА ПРОВЕРКУ" in f.values():
            errors.append(f"{sid}: осталось НА ПРОВЕРКУ")
        if f["is_claim"] not in ("да", "нет"):
            errors.append(f"{sid}: is_claim={f['is_claim']}")
            continue
        if f["is_claim"] == "нет":
            if any(f[k] for k in f if k != "is_claim"):
                errors.append(f"{sid}: у «не заявления» заполнены поля")
            continue
        if f["type"] not in TYPES: errors.append(f"{sid}: type={f['type']}")
        if f["second_type"] and (f["second_type"] not in TYPES or f["second_type"] == f["type"]):
            errors.append(f"{sid}: second_type={f['second_type']}")
        if f["esg_block"] not in BLOCK_TOPICS: errors.append(f"{sid}: esg_block={f['esg_block']}")
        elif f["topic"] != "другое" and f["topic"] not in BLOCK_TOPICS[f["esg_block"]]:
            flags.append((sid, "блок и тема", f"{f['esg_block']} / {f['topic']}", g["sentence"]))
        if f["has_number"] not in ("да", "нет"): errors.append(f"{sid}: has_number={f['has_number']}")
        if f["type"] == "обязательство" and f["has_deadline"] not in ("да", "нет"):
            errors.append(f"{sid}: у обязательства пустой has_deadline")
        if f["type"] != "обязательство" and f["has_deadline"]:
            errors.append(f"{sid}: has_deadline у типа {f['type']}")
        if f["flag"] not in FLAGS: errors.append(f"{sid}: flag={f['flag']}")

        # 3. подсказки
        s = g["sentence"]
        nums = digits_wo_years(s)
        if f["has_number"] == "да" and not nums and not NUM_WORDS.search(s):
            flags.append((sid, "число=да, а чисел нет", "", s))
        if f["has_number"] == "нет" and nums:
            flags.append((sid, "число=нет, а в тексте есть числа", " ".join(nums[:5]), s))
        if f["has_deadline"] == "да" and not (YEAR.search(s) or DATE.search(s)):
            flags.append((sid, "срок=да, а года или даты нет", "", s))
        if f["has_deadline"] == "нет" and re.search(r"\b(к|до)\s+20[2-6]\d", s):
            flags.append((sid, "срок=нет, а есть «к/до 20XX»", "", s))
        if f["type"] == "обязательство" and not FUTURE.search(s):
            flags.append((sid, "обязательство без признаков будущего", "", s))
        if f["type"] == "результат" and FUT_STRONG.search(s) and not f["second_type"] and f["flag"] != "цель изменена":
            flags.append((sid, "результат с явным будущим", FUT_STRONG.search(s).group(0), s))

    # 4. выборка
    frag_split = defaultdict(set)
    for g in gold:
        frag_split[g["fragment_id"]].add(g["split"])
    for fr, sp in frag_split.items():
        if len(sp) > 1:
            errors.append(f"{fr}: отрывок в нескольких частях {sp}")
    dup = [k for k, v in Counter(norm(g["sentence"]) for g in gold).items() if v > 1 and len(k) > 30]
    cb = "".join(norm(p.read_text(encoding="utf-8")) for p in (ROOT / "codebook").glob("Инструкция_по_разметке_v*.md"))
    in_cb = [g["sentence_id"] for g in gold if len(norm(g["sentence"])) > 60 and norm(g["sentence"]) in cb]
    for sid in in_cb:
        errors.append(f"{sid}: предложение эталона цитируется в инструкции")

    claims = [g for g in gold if g["final_is_claim"] == "да"]
    lines = ["# Проверка эталона поиска заявлений", "",
             f"Предложений: {len(gold)}, отрывков: {len(frag_split)}, отчётов: {len({g['report_id'] for g in gold})}, "
             f"компаний: {len({g['company_id'] for g in gold})}.",
             f"Заявлений: {len(claims)} — " + ", ".join(f"{k} {v}" for k, v in Counter(g['final_type'] for g in claims).most_common()),
             f"Блоки: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(g['final_esg_block'] for g in claims).items())),
             f"Обязательств со сроком: {sum(g['final_has_deadline'] == 'да' for g in claims)}",
             "", "| Часть | Предложений | Заявлений | Обязательств |", "|---|---|---|---|"]
    for key in ("split", "sample_part"):
        for v in sorted({g[key] for g in gold}):
            gs = [g for g in gold if g[key] == v]
            lines.append(f"| {v} | {len(gs)} | {sum(g['final_is_claim'] == 'да' for g in gs)} | "
                         f"{sum(g['final_type'] == 'обязательство' for g in gs)} |")
    lines += ["", f"Повторяющихся предложений: {len(dup)}", "",
              f"## Ошибки: {len(errors)}", ""] + [f"- {e}" for e in errors] + \
             ["", f"## Подсказки к ручному просмотру: {len(flags)}", "",
              "Список в `audit_flags.csv`. По видам: " + ", ".join(f"{k} {v}" for k, v in Counter(x[1] for x in flags).most_common())]
    (ROOT / "data/gold_extract/audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(ROOT / "data/gold_extract/audit_flags.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["sentence_id", "что", "детали", "предложение"])
        w.writerows(flags)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
