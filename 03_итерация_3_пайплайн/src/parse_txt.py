"""Запасной разбор отчёта, пришедшего текстом (.txt), а не PDF. Без модели.

    python -I src/parse_txt.py MVDK-2023-ГО MVDK-2025-ГО

Используется для Мосводоканала 2023 и 2025: сайт недоступен, отчёты пришли как текст без разрывов страниц.
Границы страниц восстанавливаются по строкам, где стоит только печатный номер страницы
(он идёт в конце текста страницы). Поэтому page = ПЕЧАТНЫЙ номер страницы, а не номер листа PDF.
Это отмечается в quality.csv (verdict «проверить», note). Если позже появится PDF — заменить обычным parse.py.
"""
import csv, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse import normalize, quality  # те же нормализация и метрики, что у остальных отчётов

ROOT = Path(__file__).resolve().parents[1]


def split_pages(text):
    lines = text.split("\n")
    pages, buf, cur = [], [], 0
    for ln in lines:
        m = re.fullmatch(r"\s*(\d{1,3})\s*", ln)
        if m and cur < int(m.group(1)) <= cur + 4:   # следующий номер страницы (допускаем пропуски)
            pages.append((int(m.group(1)), "\n".join(buf)))
            buf, cur = [], int(m.group(1))
        else:
            buf.append(ln)
    if "".join(buf).strip():
        pages.append((cur + 1, "\n".join(buf)))
    return pages


def main():
    qpath = ROOT / "data/pages/quality.csv"
    qrows = list(csv.DictReader(open(qpath, encoding="utf-8-sig"), delimiter=";"))
    fields = list(qrows[0].keys()) + (["note"] if "note" not in qrows[0] else [])
    for rid in sys.argv[1:]:
        out = ROOT / "data/pages" / f"{rid}.jsonl"
        if out.exists():
            print(rid, "уже есть, пропускаю"); continue
        text = (ROOT / "data/reports" / f"{rid}.txt").read_text(encoding="utf-8")
        # \x02 в этих файлах — след переноса: внутри слова строчными убираем, между прописными это дефис
        text = re.sub(r"(?<=[а-яё])\x02(?=[а-яё])", "", text)
        text = text.replace("\x02", "-")
        rows = [{"report_id": rid, "page": p, "text": normalize(t), "n_chars": len(normalize(t).strip())}
                for p, t in split_pages(text)]
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        q = quality(rid, rows)
        q["verdict"] = "проверить"
        q["note"] = "из .txt без PDF: page = печатный номер страницы"
        qrows = [r for r in qrows if r["report_id"] != rid] + [q]
        print(rid, q)
    with open(qpath, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";", restval="")
        w.writeheader(); w.writerows(sorted(qrows, key=lambda r: r["report_id"]))


if __name__ == "__main__":
    main()
