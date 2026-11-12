"""PDF -> постраничный текст (итерация 3).

Вход:  data/reports/<report_id>.pdf
Выход: data/pages/<report_id>.jsonl  ({"report_id","page","text","n_chars"} на строку)
       data/pages/quality.csv        (отчёт о качестве текста)
OCR не делаем: сканы только помечаем.
Запуск: python -I src/parse.py [папка_с_PDF]   (уже готовые jsonl не перезаписываются)

v2 (12.11.2026): текст берётся в порядке потока PDF (без sort=True). Версия v1 с sort=True
перемешивала строки соседних колонок на двухколоночных страницах; её вывод лежит в data/pages_v0_sort/ (устарело).
"""
import csv, json, re, sys, unicodedata
from pathlib import Path
import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
REPORTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "reports"
PAGES = ROOT / "data" / "pages"
QUALITY = PAGES / "quality.csv"


def normalize(t):
    t = t.replace("­", "")                      # мягкие переносы
    t = t.replace(" ", " ")                      # неразрывный пробел
    t = re.sub(r"(?<=[^\W\d_])-\n(?=[^\W\d_])", "", t)  # «эколо-\nгия» -> «экология»
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def is_bad(ch):
    if ch == "�":
        return True
    if ch in "\n\t\r ":
        return False
    return unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cs", "Cn")


def parse_one(pdf, out):
    rid = pdf.stem
    rows = []
    with fitz.open(pdf) as doc:
        for i, page in enumerate(doc, 1):
            # v2: без sort=True — иначе строки соседних колонок перемешиваются
            text = normalize(page.get_text("text"))
            rows.append({"report_id": rid, "page": i, "text": text, "n_chars": len(text.strip())})
    if not out.exists():
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def load(out):
    with open(out, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def quality(rid, rows):
    n = len(rows)
    total = sum(r["n_chars"] for r in rows)
    low = sum(1 for r in rows if r["n_chars"] < 200)
    alltext = "".join(r["text"] for r in rows)
    letters = [c for c in alltext if c.isalpha()]
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    bad = sum(1 for c in alltext if is_bad(c))
    share_empty = low / n if n else 1.0
    cyr_share = cyr / len(letters) if letters else 0.0
    bad_share = bad / len(alltext) if alltext else 0.0
    if share_empty > 0.5 or (total / n if n else 0) < 300:
        verdict = "скан"
    elif share_empty > 0.2 or cyr_share < 0.5 or bad_share > 0.01:
        verdict = "проверить"
    else:
        verdict = "хорошо"
    return {"report_id": rid, "pages": n, "chars_total": total, "pages_lt_200_chars": low,
            "share_empty": round(share_empty, 3), "cyrillic_share": round(cyr_share, 3),
            "bad_chars_share": round(bad_share, 5), "verdict": verdict}


def main():
    PAGES.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(p for p in REPORTS.glob("*.pdf") if p.is_file())
    qrows = []
    for pdf in pdfs:
        out = PAGES / f"{pdf.stem}.jsonl"
        try:
            rows = load(out) if out.exists() else parse_one(pdf, out)
            q = quality(pdf.stem, rows)
        except Exception as e:
            q = {"report_id": pdf.stem, "pages": "", "chars_total": "", "pages_lt_200_chars": "",
                 "share_empty": "", "cyrillic_share": "", "bad_chars_share": "",
                 "verdict": f"ошибка: {e}"[:200]}
        qrows.append(q)
        print(f"{q['report_id']}: {q['pages']} стр., {q['chars_total']} симв., {q['verdict']}", flush=True)
    with open(QUALITY, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(qrows)
    from collections import Counter
    print(Counter(q["verdict"] for q in qrows))


if __name__ == "__main__":
    main()
