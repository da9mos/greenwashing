#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка дословности цитат в external_facts.csv по текстам отчётов.

Для каждой строки, у которой заполнены `report_id` и `page`, проверяет, что
цитата действительно есть на этой странице `data/pages/<report_id>.jsonl`.
Нормализуются только пробелы, мягкий перенос (U+00AD) и перенос слова через
дефис — артефакты извлечения PDF. Всё остальное сравнивается как есть.

Запуск (из папки 03_итерация_3_пайплайн):
    python src/verify_fact_quotes.py

Печатает OK / HEAD (совпало до многоточия) / FAIL и подсказку с местом в тексте.
"""
import csv
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(BASE, "data", "pages")
TABLE = os.path.join(BASE, "data", "out", "external_facts.csv")


def norm(s):
    s = s.replace("\u00ad", "").replace("\u2011", "-")
    s = re.sub(r"-\s+", "", s)      # перенос слова через дефис
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


_cache = {}


def page_text(report_id, page):
    if report_id not in _cache:
        path = os.path.join(PAGES, f"{report_id}.jsonl")
        _cache[report_id] = {}
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                p = json.loads(line)
                _cache[report_id][int(p["page"])] = p.get("text") or ""
    return _cache[report_id].get(int(page), "")


def main():
    rows = list(csv.DictReader(open(TABLE, encoding="utf-8-sig"), delimiter=";"))
    bad = checked = 0
    for r in rows:
        if not r.get("report_id") or not r.get("page"):
            print(f"SKIP  {r['fact_id']}: внешний источник или нет ссылки на страницу")
            continue
        checked += 1
        txt = norm(page_text(r["report_id"], r["page"]))
        q = norm(r["quote"])
        if q in txt:
            print(f"OK    {r['fact_id']} {r['report_id']} p{r['page']}")
            continue
        head = norm(r["quote"].split("…")[0])
        if head and head in txt:
            print(f"HEAD  {r['fact_id']} {r['report_id']} p{r['page']}: совпало до многоточия")
            continue
        bad += 1
        print(f"FAIL  {r['fact_id']} {r['report_id']} p{r['page']}: {r['quote'][:70]}")
        first = norm(r["quote"].split(" ")[0])
        i = txt.find(first)
        if i >= 0:
            print("      рядом в тексте: ...", page_text(r["report_id"], r["page"])[max(0, i - 20): i + 200].replace("\n", " "))
    print(f"\nпроверено {checked}, не подтверждено {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
