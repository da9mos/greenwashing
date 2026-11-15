#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка доступности источников внешних фактов (критерий 3).

Зачем: список источников быстро устаревает — сайты включают бот-фильтры,
переезжают, отдают JS-челлендж вместо страницы. Скрипт раз в итерацию
проверяет адреса и пишет таблицу в `sources_check_auto.csv`.
Дальше человек дописывает вывод в `sources_check.md`.

Запуск (из папки 03_итерация_3_пайплайн):
    python src/check_sources.py
    python src/check_sources.py --out data/out/sources_check_auto.csv

К модели не обращается, ключей не требует.
"""
import argparse
import csv
import datetime
import subprocess

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

# (источник, url, что проверяем)
URLS = [
    ("Росприроднадзор — новости", "https://rpn.gov.ru/press/news/", "лента"),
    ("Росприроднадзор — Москва и Калужская обл.", "https://rpn.gov.ru/regions/77/news/", "новости региона"),
    ("Росприроднадзор — Тамбовская обл.", "https://rpn.gov.ru/regions/68/news/", "новости региона"),
    ("Росприроднадзор — поиск по сайту", "https://rpn.gov.ru/search/?q=%D1%88%D1%82%D1%80%D0%B0%D1%84", "поиск"),
    ("Единый реестр проверок", "https://proverki.gov.ru", "поиск проверок по ИНН"),
    ("Ростехнадзор", "https://gosnadzor.ru", "сведения об авариях"),
    ("Роструд", "https://rostrud.gov.ru", "охрана труда"),
    ("ФАС России", "https://fas.gov.ru", "антимонопольные дела"),
    ("Банк России", "https://www.cbr.ru", "нарушения на рынке ценных бумаг"),
    ("sudact.ru", "https://sudact.ru", "решения судов общей юрисдикции"),
    ("kad.arbitr.ru", "https://kad.arbitr.ru", "арбитражные дела"),
    ("Интерфакс", "https://www.interfax.ru", "новости"),
    ("ТАСС", "https://tass.ru", "новости"),
    ("РИА Новости", "https://ria.ru", "новости"),
    ("Ведомости", "https://www.vedomosti.ru", "новости"),
    ("РБК", "https://www.rbc.ru", "новости"),
    ("Violation Tracker Global", "https://violationtracker.goodjobsfirst.org", "агрегатор"),
    ("ЕГРЮЛ (налог)", "https://egrul.nalog.ru", "ИНН и ОГРН"),
]


def probe(url, timeout=20):
    p = subprocess.run(["curl", "-sS", "-m", str(timeout), "-o", "/dev/null",
                        "-w", "%{http_code};%{size_download}", "-A", UA, url],
                       capture_output=True)
    out = p.stdout.decode().strip()
    if not out:
        return "000", "0"
    code, size = out.split(";")
    return code, size


def note_for(code, size):
    if code == "000":
        return "нет соединения (таймаут/DNS/TLS)"
    if code.startswith("4"):
        return "отказ сервера (бот-фильтр/WAF)"
    if code.startswith("5"):
        return "ошибка сервера"
    if int(size) < 3000:
        return "мало байт — вероятен JS-челлендж или редирект"
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sources_check_auto.csv")
    args = ap.parse_args()

    today = datetime.date.today().isoformat()
    rows = []
    for name, url, what in URLS:
        code, size = probe(url)
        rows.append([name, url, what, code, size, note_for(code, size), today])
        print(f"{code:>3} {size:>8} {name}")

    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["источник", "url", "что проверяли", "http", "байт", "пометка", "дата_проверки"])
        w.writerows(rows)
    print(f"\nзаписано {len(rows)} строк в {args.out}")


if __name__ == "__main__":
    main()
