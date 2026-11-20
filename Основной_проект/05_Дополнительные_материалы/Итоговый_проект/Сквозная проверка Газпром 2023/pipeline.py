"""Audit the PDF/MD handoff and join claim classification to fact-check results."""
import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
PDF = PROJECT.parent / "2_итерация/Тесты_PDF_в_MD_DeepSeek_Codex/_источники/GAZP-2023-ЭО.pdf"
MD = PROJECT / "1 шаг - перевод PDF в MD/Результаты работы/Газпром 2023 - экологический отчёт/report.md"
SEED = PROJECT / "2 шаг - извлечение заявлений/Пример_Газпром_2023/claims.json"
REPORT_URL = "https://rspp.ru/upload/uf/412/mm9xy7zpgpbewr0ne387jj07aephg95u/gazprom_environmental_report_2023_ru.pdf"
MARKER = re.compile(r"<!-- pdf_page: (\d+) -->")
NUMBER = re.compile(r"(?<!\w)[−–-]?\d+(?:[,.]\d+)?")
TYPES = {"обязательство", "результат", "декларация"}
VERDICTS = {
    frozenset({"supports"}): "Подтверждено",
    frozenset({"contradicts"}): "Опровергнуто",
    frozenset({"supports", "contradicts"}): "Частично подтверждено",
}
DIMENSIONS = ("entity", "period", "metric", "unit", "boundary")
REVIEWED_ADDITIONS = (
    (18, "В структуре выбросов Группы Газпром", "Состав загрязняющих веществ в выбросах."),
    (22, "За период 2019–2023 гг. доля нормативно чистой", "Качество водоотведения за указанный период."),
    (24, "Основная масса отходов Группы Газпром", "Состав отходов по источникам образования."),
    (40, "Основным корпоративным показателем энергетической эффективности", "Метрика расходования энергоресурсов."),
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def normalize(value):
    value = unicodedata.normalize("NFKC", value).casefold().replace("\u00ad", "")
    value = re.sub(r"(?<=\w)-[ \t]*\n[ \t]*(?=\w)", "", value)
    return re.sub(r"\s+", " ", value).strip()


def load_md(path):
    parts = MARKER.split(path.read_text(encoding="utf-8"))
    numbers = list(map(int, parts[1::2]))
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError("MD page numbers must be unique and contiguous")
    pages = {}
    for number, section in zip(numbers, parts[2::2]):
        begin = "<!-- source_text_begin -->"
        end = "<!-- source_text_end -->"
        if section.count(begin) != 1 or section.count(end) != 1:
            raise ValueError(f"Page {number}: invalid source transcript boundaries")
        pages[number] = section.split(begin, 1)[1].split(end, 1)[0]
    return pages


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def read_pdf(path, use_ocr):
    layout = run("pdftotext", "-layout", str(path), "-").split("\f")
    flow = run("pdftotext", str(path), "-").split("\f")
    page_count = int(re.search(r"^Pages:\s+(\d+)", run("pdfinfo", str(path)), re.M)[1])
    if len(layout) != page_count + 1 or len(flow) != page_count + 1:
        raise ValueError("Poppler output disagrees with PDF page count")
    result = {}
    with tempfile.TemporaryDirectory() as directory:
        for page in range(1, page_count + 1):
            texts = [flow[page - 1], layout[page - 1]]
            sparse = len(re.findall(r"\w", texts[0])) < 70
            if sparse and use_ocr:
                image = Path(directory) / "page"
                run("pdftoppm", "-f", str(page), "-l", str(page), "-r", "220",
                    "-singlefile", "-png", str(path), str(image))
                texts.append(run("tesseract", str(image.with_suffix(".png")), "stdout",
                                 "-l", "rus+eng", "--psm", "3"))
            result[page] = {"texts": texts, "sparse_layer": sparse}
    return result


def audit_quote(quote, texts):
    if any(normalize(quote) in normalize(text) for text in texts[:2]):
        return "Текстовый слой PDF совпал"
    if any(normalize(quote) in normalize(text) for text in texts[2:]):
        return "Совпало по OCR. Нужна визуальная сверка"
    return "Нужна визуальная сверка PDF"


def evidence_verdict(parts, as_of, deadline=None, has_criterion=True):
    """Derive an assertion-level verdict from comparable evidence per material part."""
    if deadline and date.fromisoformat(deadline) > as_of:
        return "Срок ещё не наступил"
    if not has_criterion:
        return "Нет проверяемого критерия"
    relations = set()
    for part in parts:
        compatible = set()
        for item in part["evidence"]:
            url = urlsplit(item.get("url", ""))
            same_fact = all(part.get(key) and item.get(key) == part[key] for key in DIMENSIONS)
            if (
                item.get("reviewed") is True and item.get("independent") is True
                and item.get("original_source") is True and same_fact
                and url.scheme == "https" and url.hostname and str(item.get("quote", "")).strip()
                and str(item.get("locator", "")).strip()
                and date.fromisoformat(item["publication_date"]) <= as_of
                and item.get("relation") in {"supports", "contradicts"}
            ):
                compatible.add(item["relation"])
        if len(compatible) != 1:
            return "Недостаточно данных"
        relations.update(compatible)
    return VERDICTS.get(frozenset(relations), "Недостаточно данных")


def split_reviewed_assertions(claims, research):
    """Apply the two boundaries adjudicated against the source excerpts."""
    grouped = []
    for claim in claims:
        quote = claim["quote"]
        page = claim["page"]
        if page == 14 and "\nУвеличение произошло" in quote:
            first, second = quote.split("\n", 1)
            if (page, normalize(first)) in research:
                grouped.extend([{**claim, "quote": first}, {**claim, "quote": second}])
                continue
        if page == 38 and "выявлено 517 нарушений." in quote:
            original = next((item["quote"] for (number, text), item in research.items()
                             if number == page and normalize(quote) in text), None)
            if original:
                grouped.append({**claim, "quote": original})
                continue
        grouped.append(claim)
    return grouped


def apply_audit_corrections(claims, md):
    corrected = list(claims)
    for page, prefix, reason in REVIEWED_ADDITIONS:
        matches = [line.strip() for line in md[page].splitlines() if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f"Reviewed correction no longer matches MD on page {page}")
        quotes = matches if page != 18 else matches[0].split(" Выбросы твердых веществ", 1)
        if page == 18:
            quotes[1] = "Выбросы твердых веществ" + quotes[1]
        corrected.extend({"page": page, "quote": quote, "type": "результат", "block": "E",
                          "rule": "Аудит PDF · экологический предмет", "reason": reason}
                         for quote in quotes)
    return corrected


def display_statement(claim, quote):
    if claim["page"] == 13 and quote.startswith("|") and "\n" not in quote:
        cells = [cell.strip() for cell in quote.strip("|").split("|")]
        if len(cells) == 6 and cells[0].rstrip(".").isdigit():
            _, metric, boundary, baseline, value, status = cells
            return (f"Из таблицы. {metric}. Периметр — {boundary}. "
                    f"Базовый показатель — {baseline}. В 2023 г. — {value}. {status}.")
    return quote


def build(args):
    md = load_md(args.md)
    pdf = read_pdf(args.pdf, args.ocr)
    if md.keys() != pdf.keys():
        raise ValueError("PDF and MD physical pages disagree")
    data = read_json(args.classified) if args.classified else read_json(SEED)
    if data["source_sha256"] != sha256(args.md.read_bytes()).hexdigest():
        raise ValueError("Extraction refers to a different MD version")
    research = read_json(args.research) if args.research else {"claims": []}
    research_rows = research if isinstance(research, list) else research["claims"]
    researched = {(item["pdf_page"], normalize(item["quote"])): item for item in research_rows}
    if len(researched) != len(research_rows):
        raise ValueError("Duplicate research record")
    claims = data["claims"]
    if args.reconcile:
        claims = apply_audit_corrections(split_reviewed_assertions(claims, researched), md)
    rows = []
    keys = set()
    for claim in sorted(claims, key=lambda item: item["page"]):
        page, quote = claim["page"], claim["quote"].strip()
        if claim.get("status") == "excluded":
            continue
        if not quote or claim["type"] not in TYPES or page not in md:
            raise ValueError(f"Invalid claim on page {page}")
        key = (page, normalize(quote), claim["type"])
        if key in keys:
            continue
        keys.add(key)
        md_match = normalize(quote) in normalize(md[page])
        pdf_check = audit_quote(quote, pdf[page]["texts"])
        check = researched.get((page, normalize(quote)), {})
        parts = check.get("parts")
        verdict = evidence_verdict(parts, args.as_of, check.get("deadline"),
                                   check.get("has_criterion", True)) if parts is not None else "Недостаточно данных"
        if check.get("has_criterion") is False or (
            check and claim["type"] == "декларация" and str(check.get("verdict", "")).startswith("декларативно")
        ):
            verdict = "Нет проверяемого критерия"
        if not check:
            verdict = "Внешняя проверка не выполнена"
        block = claim.get("block") or "Требует разбора"
        if block not in {"E", "S", "G", "Требует разбора"}:
            raise ValueError(f"Invalid ESG classification on page {page}")
        rows.append({
            "number": len(rows) + 1, "page": page, "quote": quote, "type": claim["type"],
            "statement": display_statement(claim, quote),
            "block": block, "verdict": verdict, "reason": check.get("reason") or
            "Сведения из отчёта. Внешние источники по этому заявлению ещё не исследованы.",
            "classification_reason": claim.get("reason", ""), "classification_rule": claim.get("rule", ""),
            "source": f"{REPORT_URL}#page={page}", "md_match": md_match, "pdf_check": pdf_check,
            "numeric_tokens": NUMBER.findall(normalize(quote)), "research": check,
        })
    counters = Counter(row["page"] for row in rows)
    audit = {
        "pdf_sha256": sha256(args.pdf.read_bytes()).hexdigest(),
        "md_sha256": sha256(args.md.read_bytes()).hexdigest(),
        "pages": [{"page": page, "claims": counters[page], "sparse_layer": info["sparse_layer"],
                   "ocr": len(info["texts"]) > 2,
                   "ocr_characters": len(info["texts"][2].strip()) if len(info["texts"]) > 2 else 0}
                  for page, info in pdf.items()],
        "claims": len(rows), "duplicate_keys_removed": len(claims) - len(rows)
        - sum(row.get("status") == "excluded" for row in claims),
        "md_matches": sum(row["md_match"] for row in rows),
        "text_layer_matches": sum(row["pdf_check"] == "Текстовый слой PDF совпал" for row in rows),
        "classified": sum(row["block"] in {"E", "S", "G"} for row in rows),
        "verdicts": dict(Counter(row["verdict"] for row in rows)),
        "coverage_status": "пилот, семантическая полнота не установлена",
    }
    if args.independent:
        independent = read_json(args.independent)
        if independent["source_sha256"] != audit["pdf_sha256"]:
            raise ValueError("Independent audit refers to a different PDF")
        comparison = []
        for candidate in independent["candidates"]:
            excerpts = [normalize(item["quote"]) for item in candidate["evidence"]]
            matching = [
                row["number"] for row in rows if row["page"] == candidate["pdf_page"]
                and any(normalize(row["quote"]) in excerpt for excerpt in excerpts)
            ]
            comparison.append({"id": candidate["id"], "page": candidate["pdf_page"],
                               "linked_rows": matching, "reason": candidate["reason"]})
        audit["independent"] = {
            **independent["counts"],
            "passages_with_literal_overlap": sum(bool(entry["linked_rows"]) for entry in comparison),
            "passages_without_literal_overlap": sum(not entry["linked_rows"] for entry in comparison),
        }
    else:
        comparison = []
    save_json(args.output, {"audit": audit, "rows": rows, "independent_comparison": comparison})
    print(json.dumps({key: value for key, value in audit.items() if key != "pages"}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=PDF)
    parser.add_argument("--md", type=Path, default=MD)
    parser.add_argument("--classified", type=Path)
    parser.add_argument("--research", type=Path)
    parser.add_argument("--independent", type=Path)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())


if __name__ == "__main__":
    main()
