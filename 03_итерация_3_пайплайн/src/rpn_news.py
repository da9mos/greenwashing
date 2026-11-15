#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поиск новостей Росприроднадзора по компании — обход списка по региону.

Зачем: поиск на rpn.gov.ru работает через JS и скриптом не берётся
(`/search/?q=…` отдаёт пустую страницу). Зато список новостей региона
листается обычным `?PAGEN_1=N`. Поэтому ищем перебором: тянем страницы
региона и фильтруем заголовки по названию компании.

Запуск (из папки 03_итерация_3_pайплайн):
    python src/rpn_news.py --region 77 --name мосводоканал
    python src/rpn_news.py --region 68 --name пигмент --pages 420 --out data/out/rpn_68.json

К модели не обращается, ключей не требует. Пауза между запросами — 0,4 с.
"""
import argparse
import csv
import html
import json
import re
import subprocess
import sys
import time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")


def fetch(url, timeout=30):
    p = subprocess.run(["curl", "-sSL", "-m", str(timeout), "-A", UA, url],
                       capture_output=True)
    return p.stdout.decode("utf-8", "ignore")


def parse_list(page_html):
    """Возвращает список {url, title, date} со страницы списка новостей."""
    out = []
    for blk in re.split(r'(?=<a[^>]+class="[^"]*newsPreview)', page_html):
        m = re.search(r'<a[^>]+href="([^"]+)"', blk)
        if not m or "/news/" not in m.group(1):
            continue
        title_m = re.search(r"newsPreview__title[^>]*>(.*?)</", blk, re.S)
        date_m = re.search(r"newsPreview__date[^>]*>(.*?)</", blk, re.S)
        if title_m:
            title = re.sub("<[^>]+>", "", html.unescape(title_m.group(1)))
        else:
            tm = re.search(r">([^<>]{15,200})</a>", blk)
            title = html.unescape(tm.group(1)) if tm else ""
        date = ""
        if date_m:
            date = re.sub(r"<[^>]+>", "", html.unescape(date_m.group(1))).strip()
        out.append({"url": m.group(1),
                    "title": re.sub(r"\s+", " ", title).strip(),
                    "date": date})
    return out


def crawl(region, pages, stop_year):
    rows = []
    for p in range(1, pages + 1):
        url = f"https://rpn.gov.ru/regions/{region}/news/" + (f"?PAGEN_1={p}" if p > 1 else "")
        items = parse_list(fetch(url))
        if not items:
            print(f"стр. {p}: пусто, останавливаюсь", file=sys.stderr)
            break
        rows.extend(items)
        years = [int(d[-4:]) for d in (i["date"] for i in items) if re.search(r"\d{4}$", d)]
        if p % 20 == 0:
            print(f"стр. {p}: {len(rows)} новостей, до {min(years) if years else '?'} года", file=sys.stderr)
        if years and max(years) < stop_year:
            print(f"дошли до {stop_year} года, останавливаюсь", file=sys.stderr)
            break
        time.sleep(0.4)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True, help="код региона в rpn.gov.ru, напр. 77")
    ap.add_argument("--name", default=None, help="подстрока для фильтра (в нижнем регистре)")
    ap.add_argument("--pages", type=int, default=120, help="сколько страниц листать")
    ap.add_argument("--stop-year", type=int, default=2023)
    ap.add_argument("--out", default=None, help="куда сохранить весь список (json)")
    ap.add_argument("--csv", default=None, help="куда сохранить совпадения (csv)")
    args = ap.parse_args()

    rows = crawl(args.region, args.pages, args.stop_year)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"сохранено {len(rows)} новостей в {args.out}", file=sys.stderr)

    hits = rows
    if args.name:
        n = args.name.lower()
        hits = [r for r in rows if n in (r["title"] + " " + r["url"]).lower()]

    print(f"всего {len(rows)}, совпадений {len(hits)}")
    for r in hits:
        print(f"{r['date']:>15} | {r['title'][:90]} | https://rpn.gov.ru{r['url']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["дата", "заголовок", "url"])
            for r in hits:
                w.writerow([r["date"], r["title"], "https://rpn.gov.ru" + r["url"]])
        print(f"совпадения записаны в {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
