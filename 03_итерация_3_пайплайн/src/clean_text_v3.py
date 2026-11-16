"""Чистка текстов отчётов, версия v3. Без модели. Старые файлы не меняет.

    python src/clean_text_v3.py

Вход:  data/pages/*.jsonl (v2, как есть), data/reports/MVDK-2023-ГО.txt и MVDK-2025-ГО.txt
Выход: data/pages_v3/<report_id>.jsonl   тексты по страницам после чистки (тот же формат, что v2)
       data/pages_v3/quality.csv         качество текста v3 (с проверкой странных символов)
       data/text_v3/quality_v2_перепроверка.csv   та же проверка на старых текстах v2
       data/text_v3/замены_дефис.csv      какие слова через дефис восстановлены и сколько раз
       data/text_v3/колонтитулы.csv       какие повторяющиеся строки убраны в каком отчёте
       data/text_v3/шрифт_MAGN-2025.csv   замены значков сломанного шрифта ММК 2025 по страницам

Что исправляется (найдено при проверке 16.11.2026, см. data/text_v3/README.md):
1. ММК 2025: сломанный шрифт. Цифры записаны знаками U+0510–U+0519 и U+0526–U+052F (по порядку 0–9),
   заглавные буквы — знаками U+0300–U+0320 (А–Я с Ё), строчные — U+032F–U+034F (а–я с ё).
   Замена однозначная, проверена по картинке страницы 12. Остальные значки (армянские, арабские:
   сноски, стрелки, знак %) не угадываются и остаются; их считает quality.csv.
2. Склеенные слова через дефис: parse.py v2 убирал дефис в конце строки как перенос и склеивал
   «научно-/исследовательских» в «научноисследовательских». Дефис возвращается, если в корпусе есть
   то же слово с дефисом и (а) с дефисом оно встречается не реже, чем без, или (б) первая часть —
   частая приставка составных слов (научно-, социально-, бизнес-, Санкт- …).
3. Колонтитулы и меню: строка, которая повторяется на ≥50 % страниц отчёта (≥12 знаков), или на ≥30 %
   страниц и почти всегда стоит в первых/последних трёх строках страницы (≥8 знаков), убирается.
4. Мосводоканал 2023 и 2025 (из .txt): номер страницы бывает приклеен к концу строки после знака
   переноса (\x02), например «ско\x0268». Такие границы страниц теперь тоже распознаются.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from parse import normalize  # noqa: E402  та же нормализация, что в v2

SRC = ROOT / "data" / "pages"
DST = ROOT / "data" / "pages_v3"
REP = ROOT / "data" / "text_v3"

# ---------- 1. сломанный шрифт ----------
BROKEN_FONT_REPORTS = {"MAGN-2025-ИО"}
UPPER = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
LOWER = UPPER.lower()
GLYPH = {}
for i in range(10):
    GLYPH[chr(0x510 + i)] = str(i)
    GLYPH[chr(0x526 + i)] = str(i)
for i, ch in enumerate(UPPER):
    GLYPH[chr(0x300 + i)] = ch
for i, ch in enumerate(LOWER):
    GLYPH[chr(0x32F + i)] = ch
GLYPH["\u0668"] = "↑"   # стрелки в плашках «к 2024 году», сверено по стр. 12
GLYPH["\u066C"] = "↓"
GLYPH["\u0653"] = "%"
GLYPH["\x06"] = "."      # точка: «п\x06 п\x06» = «п. п.», «млн РУБ\x06» = «млн руб.»
GLYPH["\u0450"] = "ер"  # «ѐ» = е + U+0340 (р), Unicode склеивает их в одну букву
MARK = re.compile("[̀-͏]")


def fix_font(text: str, log: Counter | None = None) -> str:
    out = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch in GLYPH:
            rep = GLYPH[ch]
            if log is not None:
                log[(ch, rep)] += 1
            if MARK.match(ch):
                prev = out[-1][-1] if out and out[-1] else ""
                nxt = text[i + 1] if i + 1 < n else ""
                nxt2 = text[i + 2] if i + 2 < n else ""
                if rep.isupper() and prev.islower():
                    rep = " " + rep                    # «в̔ ральском» -> «в Уральском»
                # шрифт ставит после буквы-значка лишний пробел или перенос строки: «̒ овета» -> «Совета»
                if nxt in " \n" and nxt2.isalpha():
                    out.append(rep)
                    i += 2
                    continue
            out.append(rep)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


# ---------- 2. дефис ----------
WORD = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")
# Приставки, с которыми составные слова пишутся через дефис. Сюда не входят горно-, геолого-, нефте-
# и подобные: «горнорудный», «геологоразведочный» пишутся слитно.
PREFIX_OK = {"научно", "социально", "бизнес", "санкт", "топливно", "материально", "опытно", "финансово",
             "человеко", "санаторно", "аварийно", "информационно", "инженерно", "технико", "риск", "мастер",
             "вице", "северо", "южно", "восточно", "западно", "медико", "учебно", "физкультурно", "нормативно",
             "административно", "организационно", "культурно", "историко", "химико", "физико", "санитарно",
             "пожарно", "ремонтно", "контрольно", "проектно", "торгово", "транспортно", "хозяйственно",
             "эколого", "военно", "лечебно", "общественно", "онлайн", "офлайн", "пресс", "кросс", "экспресс",
             "комплаенс", "фитнес", "интернет", "дизайн"}


def build_hyphen_map(texts) -> dict[str, int]:
    """Возвращает {склеенное_слово_строчными: позиция_дефиса}."""
    cnt = Counter()
    for t in texts:
        cnt.update(w.lower() for w in WORD.findall(t))
    prefixes = defaultdict(set)
    for w in cnt:
        if w.count("-") == 1:
            a, b = w.split("-")
            if len(a) >= 4 and len(b) >= 3:
                prefixes[a].add(b)
    productive = {a for a, s in prefixes.items() if len(s) >= 5 and a in PREFIX_OK}
    out = {}
    for w, c in cnt.items():
        if w.count("-") != 1:
            continue
        a, b = w.split("-")
        if len(a) < 2 or len(b) < 3 or (len(a) < 4 and a not in PREFIX_OK):
            continue
        joined = a + b
        jc = cnt.get(joined, 0)
        if not jc:
            continue
        if c >= jc or a in productive:
            out[joined] = len(a)
    return out


def fix_hyphens(text: str, hmap: dict[str, int], log: Counter | None = None) -> str:
    def rep(m):
        w = m.group(0)
        pos = hmap.get(w.lower())
        if pos is None:
            return w
        new = w[:pos] + "-" + w[pos:]
        if log is not None:
            log[(w.lower(), new.lower())] += 1
        return new
    return re.sub(r"(?<![-А-Яа-яЁё])[А-Яа-яЁё]+(?![-А-Яа-яЁё])", rep, text)


# ---------- 3. колонтитулы ----------
def header_lines(pages: list[str]) -> dict[str, int]:
    n = len(pages)
    if n < 8:
        return {}
    occ, edge = Counter(), Counter()
    for t in pages:
        lines = [l.strip() for l in t.split("\n") if l.strip()]
        ends = set(lines[:3] + lines[-3:])
        for l in set(lines):
            occ[l] += 1
            if l in ends:
                edge[l] += 1
    found = {}
    for l, c in occ.items():
        if not re.search(r"[А-Яа-яЁёA-Za-z]{3}", l):
            continue
        if (len(l) >= 12 and c >= 0.5 * n) or (len(l) >= 8 and c >= 0.3 * n and edge[l] >= 0.8 * c):
            found[l] = c
    return found


def strip_headers(text: str, heads: dict[str, int]) -> str:
    if not heads:
        return text
    return "\n".join(l for l in text.split("\n") if l.strip() not in heads)


# ---------- 4. Мосводоканал ----------
def split_pages_txt(text: str):
    """Как parse_txt.split_pages, но ещё ловит номер страницы, приклеенный после знака переноса."""
    lines = text.split("\n")
    nums = [re.fullmatch(r"\s*(\d{1,3})\s*", ln) for ln in lines]

    def skipped_soon(i, cur, n):
        # число из графика (например «70» на оси) принимаем за номер страницы, только если
        # пропущенные номера cur+1 … n-1 не встречаются отдельной строкой в ближайших 300 строках
        want = {str(k) for k in range(cur + 1, n)}
        return any(m and m.group(1) in want for m in nums[i + 1:i + 300])

    pages, buf, cur = [], [], 0
    for i, ln in enumerate(lines):
        m = nums[i]
        g = re.fullmatch(r"(.*\x02)(\d{1,3})[ \t]*", ln)
        if m and cur < int(m.group(1)) <= cur + 4 and not skipped_soon(i, cur, int(m.group(1))):
            pages.append((int(m.group(1)), "\n".join(buf)))
            buf, cur = [], int(m.group(1))
        elif g and cur < int(g.group(2)) <= cur + 4:
            buf.append(g.group(1))           # слово переносится на следующую страницу
            pages.append((int(g.group(2)), "\n".join(buf)))
            buf, cur = [], int(g.group(2))
        else:
            buf.append(ln)
    if "".join(buf).strip():
        pages.append((cur + 1, "\n".join(buf)))
    # перенос через границу страницы: конец слова на следующей странице приклеиваем к ней
    fixed = []
    for p, t in pages:
        t = re.sub(r"(?<=[а-яё])\x02(?=[а-яё])", "", t)
        t = re.sub(r"(?<=[а-яё])\x02$", "-", t)   # хвост слова ушёл на следующую страницу
        fixed.append((p, t.replace("\x02", "-")))
    return fixed


TXT_REPORTS = ["MVDK-2023-ГО", "MVDK-2025-ГО"]

# ---------- качество ----------


def is_odd(ch: str) -> bool:
    o = ord(ch)
    if ch in "\n\t\r\x07\x08":   # \x07 и \x08 — маркеры списка и табуляции в вёрстке, текст не портят
        return False
    return (0x300 <= o <= 0x36F or 0x500 <= o <= 0x58F or 0x600 <= o <= 0x6FF or 0xE000 <= o <= 0xF8FF
            or o == 0xFFFD or o < 32)


def quality(rid: str, rows: list[dict], glued: int) -> dict:
    n = len(rows)
    total = sum(r["n_chars"] for r in rows)
    low = sum(1 for r in rows if r["n_chars"] < 200)
    alltext = "".join(r["text"] for r in rows)
    letters = [c for c in alltext if c.isalpha()]
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    odd = sum(1 for c in alltext if is_odd(c))
    odd_pages = sum(1 for r in rows if sum(1 for c in r["text"] if is_odd(c)) > max(5, 0.01 * len(r["text"])))
    share_empty = low / n if n else 1.0
    cyr_share = cyr / len(letters) if letters else 0.0
    odd_share = odd / len(alltext) if alltext else 0.0
    notes = []
    if share_empty > 0.5 or (total / n if n else 0) < 300:
        verdict = "скан"
    else:
        verdict = "хорошо"
        if share_empty > 0.2:
            notes.append("много пустых страниц")
        if cyr_share < 0.9:
            notes.append(f"мало кириллицы ({cyr_share:.2f})")
        if odd_pages > 0.05 * n or odd_pages >= 5:
            notes.append(f"странные знаки на {odd_pages} стр.")
        if notes:
            verdict = "проверить"
    return {"report_id": rid, "pages": n, "chars_total": total, "pages_lt_200_chars": low,
            "share_empty": round(share_empty, 3), "cyrillic_share": round(cyr_share, 3),
            "odd_chars": odd, "odd_chars_share": round(odd_share, 5), "pages_with_odd_chars": odd_pages,
            "glued_hyphen_words": glued, "verdict": verdict, "note": "; ".join(notes)}


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main() -> None:
    if DST.exists() and any(DST.glob("*.jsonl")):
        sys.exit(f"{DST} уже заполнена: v3 не перезаписываем. Для новой версии сделайте pages_v4.")
    DST.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)

    reports = {f.stem: load(f) for f in sorted(SRC.glob("*.jsonl"))}
    # Мосводоканал 2023/2025 — заново из .txt
    for rid in TXT_REPORTS:
        txt = ROOT / "data" / "reports" / f"{rid}.txt"
        if txt.exists():
            reports[rid] = [{"report_id": rid, "page": p, "text": normalize(t), "n_chars": len(normalize(t).strip())}
                            for p, t in split_pages_txt(txt.read_text(encoding="utf-8"))]

    font_log = Counter()
    font_pages = []
    for rid in BROKEN_FONT_REPORTS & set(reports):
        for r in reports[rid]:
            before = r["text"]
            r["text"] = fix_font(before, font_log)
            if r["text"] != before:
                font_pages.append({"report_id": rid, "page": r["page"],
                                   "знаков_заменено": sum(1 for c in before if c in GLYPH)})

    hmap = build_hyphen_map(r["text"] for rows in reports.values() for r in rows)

    qv2, qv3, heads_out = [], [], []
    hyph_log = Counter()
    for rid, rows in reports.items():
        old_rows = load(SRC / f"{rid}.jsonl")
        glued_old = sum(1 for r in old_rows for w in re.findall(r"[А-Яа-яЁё]+", r["text"]) if w.lower() in hmap)
        qv2.append(quality(rid, old_rows, glued_old))

        heads = header_lines([r["text"] for r in rows])
        for l, c in sorted(heads.items(), key=lambda t: -t[1]):
            heads_out.append({"report_id": rid, "строка": l, "страниц": c, "всего_страниц": len(rows)})
        log = Counter()
        out_rows = []
        for r in rows:
            t = strip_headers(r["text"], heads)
            t = fix_hyphens(t, hmap, log)
            out_rows.append({"report_id": rid, "page": r["page"], "text": t, "n_chars": len(t.strip())})
        hyph_log.update(log)
        glued_new = sum(1 for r in out_rows for w in re.findall(r"(?<![-А-Яа-яЁё])[А-Яа-яЁё]+(?![-А-Яа-яЁё])", r["text"])
                        if w.lower() in hmap)
        q = quality(rid, out_rows, glued_new)
        if rid in TXT_REPORTS:
            q["verdict"] = "проверить"
            q["note"] = "; ".join(x for x in [q["note"], "из .txt без PDF: page = печатный номер страницы"] if x)
        if rid in BROKEN_FONT_REPORTS:
            q["note"] = "; ".join(x for x in [q["note"], "сломанный шрифт исправлен заменой, сноски и стрелки остались значками"] if x)
            q["verdict"] = "проверить"
        qv3.append(q)
        with open(DST / f"{rid}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for r in out_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{rid}: {len(out_rows)} стр., колонтитулов {len(heads)}, дефисов {sum(log.values())}", flush=True)

    write_csv(DST / "quality.csv", qv3)
    write_csv(REP / "quality_v2_перепроверка.csv", qv2)
    write_csv(REP / "колонтитулы.csv", heads_out, ["report_id", "строка", "страниц", "всего_страниц"])
    write_csv(REP / "замены_дефис.csv",
              [{"было": a, "стало": b, "раз": c} for (a, b), c in hyph_log.most_common()], ["было", "стало", "раз"])
    write_csv(REP / "шрифт_MAGN-2025.csv",
              [{"значок": f"U+{ord(a):04X}", "стало": b, "раз": c} for (a, b), c in font_log.most_common()],
              ["значок", "стало", "раз"])
    write_csv(REP / "шрифт_MAGN-2025_страницы.csv", font_pages, ["report_id", "page", "знаков_заменено"])
    print("v2:", Counter(q["verdict"] for q in qv2), "| v3:", Counter(q["verdict"] for q in qv3))
    print("дефисов восстановлено:", sum(hyph_log.values()), "разных слов:", len(hyph_log))


if __name__ == "__main__":
    main()
