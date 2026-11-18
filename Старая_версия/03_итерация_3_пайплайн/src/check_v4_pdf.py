"""Сверка текстов v4 с PDF на свежей случайной выборке, другим разборщиком (pdftotext из poppler). Без модели.

    python -I src/check_v4_pdf.py <папка с PDF>

Зачем другой разборщик: v4 получен через PyMuPDF; pdftotext читает PDF своим кодом, поэтому общие
ошибки (пропавший текст, неверные буквы шрифта, чужая страница) он не повторит. Режим -raw: порядок
текста как в самом PDF и без собственной склейки переносов (обычный режим pdftotext склеивает их сам).

Выборка новая (зерно 20261116), не та, на которой подбирались правила. Три части:
  1. Страницы: по 3 случайные страницы каждого отчёта с PDF. Буквы и цифры страницы v4 (+ убранные
     колонтитулы) сравниваются с буквами pdftotext той же страницы как набор. Расхождение > 2% — «проверить».
  2. Цитаты: 150 случайных заявлений и 150 предложений эталона. Буквы цитаты v4 должны найтись подряд
     в буквах pdftotext той же страницы.
  3. Переносы: до 300 случайных мест (по 60: решение по самому PDF; слитно без довода из PDF; через дефис
     без довода из PDF; оставлен перенос строки; висячий дефис/мягкий перенос) с окружением из pdftotext — для просмотра глазами.
ММК 2025 и ТМК 2023 в частях 1–2 считаются отдельно: у них битый шрифт, pdftotext тоже видит значки.
Выход (не перезаписывает): data/text_v4/сверка_PDF_страницы.csv, сверка_PDF_цитаты.csv,
сверка_PDF_переносы.csv, сверка_PDF_итог.md
"""
from __future__ import annotations

import csv
import json
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "data" / "pages_v4"
REP = ROOT / "data" / "text_v4"
SEED = 20261116
BROKEN_FONT = {"MAGN-2025-ИО", "TRMK-2023-ИО"}


def letters(s: str) -> str:
    return "".join(ch.lower().replace("ё", "е") for ch in s if ch.isalnum())


def read_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write_csv(p: Path, rows: list[dict]) -> None:
    with open(p, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)


def v4_pages(rid: str) -> dict[int, str]:
    with open(V4 / f"{rid}.jsonl", encoding="utf-8") as f:
        return {int(r["page"]): r["text"] for r in map(json.loads, f)}


def v2_pages(rid: str) -> dict[int, str]:
    with open(ROOT / "data/pages" / f"{rid}.jsonl", encoding="utf-8") as f:
        return {int(r["page"]): r["text"] for r in map(json.loads, f)}


def base_pages(rid: str) -> dict[int, str]:
    """Текст до чистки колонтитулов: v2, для ММК 2025 — с исправленным шрифтом."""
    if rid == "MAGN-2025-ИО":
        with open(REP / f"база_{rid}.jsonl", encoding="utf-8") as f:
            return {int(r["page"]): r["text"] for r in map(json.loads, f)}
    return v2_pages(rid)


_cache: dict[tuple[str, int], str] = {}


def poppler(pdf: Path, page: int) -> str:
    k = (str(pdf), page)
    if k not in _cache:
        _cache[k] = subprocess.run(["pdftotext", "-q", "-raw", "-enc", "UTF-8", "-f", str(page), "-l", str(page), str(pdf), "-"],
                                   capture_output=True, text=True, check=True).stdout.replace("­", "")
    return _cache[k]


def main() -> None:
    pdf_dir = Path(sys.argv[1])
    outs = [REP / f"сверка_PDF_{n}" for n in ("страницы.csv", "цитаты.csv", "переносы.csv", "итог.md")]
    if any(p.exists() for p in outs):
        sys.exit("файлы сверки уже есть, не перезаписываю")
    rnd = random.Random(SEED)
    heads = defaultdict(set)
    for r in read_csv(REP / "колонтитулы.csv"):
        heads[r["report_id"]].add(r["строка"])
    rids = sorted(p.stem for p in V4.glob("*.jsonl") if (pdf_dir / f"{p.stem}.pdf").exists())

    # 1. страницы
    prow = []
    for rid in rids:
        pg = v4_pages(rid)
        for p in sorted(rnd.sample(sorted(pg), min(3, len(pg)))):
            base = base_pages(rid)[p]
            # v4 + строки колонтитулов, которые v4 убрал с этой страницы
            removed = "".join(l for l in base.split("\n") if l.strip() in heads[rid])
            a = Counter(letters(pg[p] + removed))
            a2 = Counter(letters(v2_pages(rid)[p]))
            b = Counter(letters(poppler(pdf_dir / f"{rid}.pdf", p)))
            share = sum(((a - b) + (b - a)).values()) / max(1, sum(b.values()))
            share2 = sum(((a2 - b) + (b - a2)).values()) / max(1, sum(b.values()))
            itog = ("совпало" if share <= 0.02 else
                    "битый шрифт (известно)" if rid in BROKEN_FONT else
                    "так же в v2: в PDF есть текст, который PyMuPDF не выдаёт" if abs(share - share2) <= 0.005 else
                    "проверить")
            prow.append({"report_id": rid, "page": p, "букв_v4": sum(a.values()), "букв_pdftotext": sum(b.values()),
                         "расхождение": f"{share:.4f}", "расхождение_v2": f"{share2:.4f}", "итог": itog})
    write_csv(outs[0], prow)

    # 2. цитаты
    qrow = []
    for path, idcol, tcol in ((ROOT / "data/out/claims_text_v4.csv", "claim_id", "text"),
                              (ROOT / "data/out/gold_extract_text_v4.csv", "sentence_id", "sentence")):
        rows = [r for r in read_csv(path) if (pdf_dir / f"{r['report_id']}.pdf").exists()]
        for r in rnd.sample(rows, min(150, len(rows))):
            pg = int(r["page"])
            q = letters(r[tcol])
            near = "".join(letters(poppler(pdf_dir / f"{r['report_id']}.pdf", p))
                           for p in (pg - 1, pg, pg + 1) if p >= 1)
            same = q in letters(poppler(pdf_dir / f"{r['report_id']}.pdf", pg))
            words = Counter(re.findall(r"\w+", r[tcol].lower().replace("ё", "е")))
            pw = Counter(re.findall(r"\w+", poppler(pdf_dir / f"{r['report_id']}.pdf", pg).lower().replace("ё", "е")))
            itog = ("на той же странице PDF" if same else
                    "на стыке страниц PDF" if q in near else
                    "все слова на той же странице PDF (в PDF другой порядок колонок)" if not words - pw else
                    "битый шрифт (известно)" if r["report_id"] in BROKEN_FONT else "проверить")
            qrow.append({"таблица": path.name, "id": r[idcol], "report_id": r["report_id"], "page": pg,
                         "check_v4": r["check_v4"], "итог": itog, "цитата": r[tcol][:200]})
    write_csv(outs[1], qrow)

    # 3. переносы
    br = [r for r in read_csv(REP / "переносы.csv") if (pdf_dir / f"{r['report_id']}.pdf").exists()]
    groups = {
        "по самому PDF": [r for r in br if r["довод"].startswith("PDF ")],
        "слитно без довода из PDF": [r for r in br if r["решение"] == "слитно" and not r["довод"].startswith(("PDF ", "мягкий"))],
        "через дефис без довода из PDF": [r for r in br if r["решение"] == "через дефис" and not r["довод"].startswith("PDF ")],
        "оставлен перенос строки": [r for r in br if r["решение"] == "перенос строки"],
        "висячий дефис / мягкий перенос": [r for r in br if r["решение"] == "висячий дефис" or r["вид"] == "мягкий перенос"],
    }
    hrow = []
    for g, rows in groups.items():
        for r in rnd.sample(rows, min(60, len(rows))):
            t = poppler(pdf_dir / f"{r['report_id']}.pdf", int(r["page"]))
            m = re.search(re.escape(r["слева"]) + r"\W{0,4}\n\s*" + re.escape(r["справа"]), t)
            ctx = re.sub(r"\s+", " ", t[max(0, m.start() - 40):m.end() + 40]) if m else ""
            mid = {"слитно": "", "через дефис": "-", "висячий дефис": "- ", "перенос строки": "-⏎"}[r["решение"]]
            hrow.append({"группа": g, "report_id": r["report_id"], "page": r["page"],
                         "в_v4": r["слева"] + mid + r["справа"], "довод": r["довод"],
                         "перенос_есть_в_pdftotext": "да" if m else "нет", "окружение_pdftotext": ctx})
    write_csv(outs[2], hrow)

    lines = ["# Сверка v4 с PDF (pdftotext, свежая выборка, зерно %d)" % SEED, ""]
    for name, rows in (("Страницы", prow), ("Цитаты", qrow)):
        c = Counter(r["итог"] for r in rows)
        lines += [f"## {name}: {len(rows)}", ""] + [f"- {k}: {v}" for k, v in c.most_common()] + [""]
        lines += [f"  - {r['report_id']} стр. {r['page']}: {r.get('расхождение') or r.get('id')}"
                  for r in rows if r["итог"] == "проверить"] + [""]
    c = Counter((r["группа"], r["перенос_есть_в_pdftotext"]) for r in hrow)
    lines += [f"## Переносы: {len(hrow)} (просмотр глазами — см. сверка_PDF_переносы.csv)", ""]
    lines += [f"- {g}: перенос виден в pdftotext {v}" for (g, k), v in sorted(c.items()) if k == "да"]
    with open(outs[3], "x", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
