"""Сведения из самих PDF для текстов v4. Без модели. Нужны PDF (data/reports или путь в аргументе).

    python -I src/pdf_evidence_v4.py [папка_с_PDF]

Зачем. Чистка v3 (16.11.2026) решала, ставить ли дефис, по словарю, собранному из уже испорченного
текста v2, и чинила шрифт ММК 2025 заменой значков. Независимая проверка нашла, что так дефис
иногда ставится там, где в PDF слово написано слитно («рискориентированный», «Новосакмарского»),
а знак «№» в ММК 2025 превращается в цифру 9, латиница сдвигается («GRI» → «JUL»).
Этот скрипт берёт ответ из самого PDF и сохраняет его в небольшие файлы. Дальше
src/clean_text_v4.py собирает тексты v4 уже без PDF, только по этим файлам.

Что делает:
1. Для каждого PDF повторяет разбор parse.py (PyMuPDF, порядок потока) и проверяет, что текст
   совпадает с data/pages (v2) символ в символ. Если не совпал — остановка: версия PyMuPDF другая.
2. Находит каждый перенос слова на странице: дефис в конце строки (v2 его убрал и склеил слово),
   мягкий перенос (U+00AD, v2 оставил разрыв строки посреди слова), дефис с пробелом перед
   концом строки и неразрывный дефис (v2 оставил как есть). Для каждого записывает место
   (страница и позиция в тексте v2) и решение: слитно, через дефис, висячий дефис
   («энерго- и ресурсосбережение») или «перенос строки» (оставить дефис и конец строки, как в PDF:
   дальше слово с заглавной — по сверке 16.11 это почти всегда строка из другой колонки). Решение берётся из того же PDF: как это слово написано
   внутри строки, где переноса нет (сначала в этом отчёте, потом во всех 92). Правила
   (составные приставки, имена собственные) — только если в PDF такого слова внутри строки нет.
3. ММК 2025: часть шрифта TT Hoves Pro вшита без таблицы «знак → буква». Для таких знаков
   PyMuPDF выдаёт номер рисунка буквы в шрифте вместо самой буквы. Номер рисунка → буква:
   из таблиц того же шрифта, где они есть (ToUnicode), и по правилу семейства шрифта; правило
   сверено со всеми номерами, у которых таблица есть (0 расхождений), а номера без таблицы
   опознаны по картинкам страниц. Затем в копии PDF в памяти (файл не меняется) всем частям
   шрифта ставится полная таблица, и текст разбирается заново тем же PyMuPDF: буквы получают
   нормальную ширину, поэтому и пробелы встают на места. Страницы, где сломанных знаков не было,
   обязаны совпасть с v2 символ в символ. Результат: data/text_v4/база_MAGN-2025-ИО.jsonl.

Выход (data/text_v4/, готовые файлы не перезаписываются):
  переносы.csv                  все переносы с решением и доводами
  база_MAGN-2025-ИО.jsonl       страницы ММК 2025 с исправленным шрифтом (как v2, но буквы верные)
  шрифт_MAGN-2025_таблица.csv   номер рисунка → буква, откуда известно, сколько раз встретилось
  pdf_источники.csv             хэши PDF и версия PyMuPDF, на которых получены эти файлы
"""
from __future__ import annotations

import bisect
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from parse import normalize  # noqa: E402  нормализация v2
from clean_text_v3 import split_pages_txt, TXT_REPORTS  # noqa: E402  границы страниц Мосводоканала v3

OUT = ROOT / "data" / "text_v4"
V2 = ROOT / "data" / "pages"

LETTER = "A-Za-zА-Яа-яЁё"
HY = "-‐‑"
TOKEN = re.compile(rf"[{LETTER}]+(?:[{HY}][{LETTER}]+)*")
SUSPENDED = {"и", "или", "либо"}   # «энерго- и ресурсосбережение»: висячий дефис
# Первые части составных слов, которые пишутся через дефис. Используются, только если в PDF
# нет того же слова внутри строки. Сюда нарочно не входят горно-, нефте-, газо-, энерго-, водо-,
# электро-: с ними слова чаще пишутся слитно («горнодобывающий», «водоснабжение»).
PREFIX_OK = {"научно", "социально", "бизнес", "санкт", "топливно", "материально", "опытно", "финансово",
             "человеко", "санаторно", "аварийно", "информационно", "инженерно", "технико", "риск", "мастер",
             "вице", "северо", "южно", "восточно", "западно", "медико", "учебно", "физкультурно", "нормативно",
             "административно", "организационно", "культурно", "историко", "химико", "физико", "санитарно",
             "пожарно", "ремонтно", "контрольно", "проектно", "торгово", "транспортно", "хозяйственно",
             "эколого", "военно", "лечебно", "общественно", "онлайн", "офлайн", "пресс", "кросс", "экспресс",
             "комплаенс", "фитнес", "интернет", "дизайн", "производственно", "товарно", "жилищно",
             "строительно", "спортивно", "профессионально", "социально", "юго", "северо", "ямало", "ханты"}

# Первые части, с которыми слова пишутся слитно («светодинамические», «высокоурбанизированных»)
GLUED_FIRST = {"свето", "тонко", "пиро", "лесо", "азото", "кардио", "высоко", "глубоко", "низко", "мало", "много",
               "крупно", "мелко", "средне", "трудно", "легко", "широко", "узко", "сильно", "слабо", "остро", "быстро",
               "долго", "коротко", "тяжело", "густо", "редко", "энерго", "электро", "водо", "газо", "нефте", "тепло",
               "гидро", "термо", "радио", "фото", "видео", "авто", "агро", "био", "эко", "гео", "микро", "макро",
               "мульти", "поли", "моно", "теле", "аэро", "ново", "старо", "горно", "лесо", "рыбо", "звуко",
               "свето", "паро", "пыле", "шламо", "золо", "нефтегазо", "углево", "дорого", "дёшево", "дешево"}

# Начала, с которых обычно начинается вторая половина слова при переносе («прочными», «Селезневского»):
# такая «вторая часть» не считается отдельным словом, даже если где-то встречается сама по себе.
TAILS = ("ск", "ств", "чик", "щик", "чиц", "щиц", "ющ", "ящ", "ующ", "ными", "ному", "ного", "ной", "ные", "ник", "ниц", "ние", "ния", "нию",
         "ниям", "ност", "ческ", "тель", "ваш", "ван", "вани", "ема", "емы", "ого", "его", "ому", "ыми", "ими")

M_JOIN = ""   # здесь normalize() склеил «дефис + конец строки»
M_SOFT = ""   # здесь стоял мягкий перенос перед концом строки


# ---------- 1. ММК 2025: шрифт без таблицы знаков ----------
BROKEN_FONT = {"MAGN-2025-ИО": "TTHovesPro"}
_UP = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"


def hoves_rule() -> dict[int, str]:
    """Номер рисунка → знак для TT Hoves Pro (порядок рисунков одинаков во всех начертаниях).
    Кириллица, цифры и надстрочные — по порядку; знаки ниже — по ToUnicode и по картинкам."""
    r = {3: " ", 4: " ", 5: "·", 6: ".", 8: ",", 9: ":", 10: ":", 11: ";", 12: "!", 14: "?", 24: "*",
         26: '"', 0x23: "«", 0x24: "»", 0x26: "-", 0x28: "–", 0x29: "—", 0x2B: "(", 0x2C: ")", 53: "/",
         57: "№", 59: "&", 67: "@", 170: "İ", 213: "Ş", 226: "Ü", 350: "ü", 525: "ffi", 526: "fi", 530: "fl",
         1487: "$", 1591: "−", 1592: "+", 1593: "<", 1594: ">", 1597: "=", 1603: "×", 1619: "%",
         1639: "°", 1640: "↑", 1642: "→", 1644: "↓"}
    for i in range(26):
        r[68 + i] = chr(65 + i)      # A–Z: номер = код + 3 («GRI» печаталось как «JUL»)
        r[94 + i] = chr(97 + i)      # a–z: номер = код − 3
    for i, c in enumerate(_UP):
        r[768 + i] = c
        r[815 + i] = c.lower()
    for i in range(10):
        r[1296 + i] = str(i)
        r[1318 + i] = str(i)
        r[1364 + i] = "⁰¹²³⁴⁵⁶⁷⁸⁹"[i]
        r[1374 + i] = "₀₁₂₃₄₅₆₇₈₉"[i]
    return r


# Номера, опознанные по картинкам страниц (проверка 16.11.2026, листы с вырезками рисунков)
SEEN_ON_IMAGE = {5, 10, 12, 14, 26, 40, 57, 59, 78, 79, 82, 83, 84, 88, 90, 91, 92, 93, 95, 98, 99, 101, 103,
                 104, 105, 108, 109, 112, 113, 114, 116, 117, 118, 170, 213, 226, 350, 526, 530, 768, 771, 773,
                 775, 776, 777, 778, 780, 781, 782, 783, 785, 786, 788, 791, 792, 794, 796, 797, 798, 800, 818,
                 821, 822, 840, 1318, 1319, 1320, 1321, 1323, 1324, 1325, 1327, 1364, 1365, 1366, 1367, 1370,
                 1371, 1372, 1373, 1376, 1377, 1487, 1593, 1594, 1597, 1603, 1639, 1640, 1642, 1644}


def tounicode_table(doc, family: str) -> dict[int, str]:
    out: dict[int, Counter] = defaultdict(Counter)
    seen = set()
    for page in doc:
        for f in page.get_fonts(full=True):
            xref, _, typ, name = f[:4]
            if xref in seen or typ != "Type0" or family not in name:
                continue
            seen.add(xref)
            tu = doc.xref_get_key(xref, "ToUnicode")
            if tu[0] != "xref":
                continue
            s = doc.xref_stream(int(tu[1].split()[0])).decode("latin1")
            body = s.split("endcodespacerange", 1)[-1]
            for blk in re.findall(r"beginbfchar(.*?)endbfchar", body, re.S):
                for a, b in re.findall(r"<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]+)>", blk):
                    out[int(a, 16)]["".join(chr(int(b[i:i + 4], 16)) for i in range(0, len(b), 4))] += 1
            for blk in re.findall(r"beginbfrange(.*?)endbfrange", body, re.S):
                for a, z, b in re.findall(r"<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4})>", blk):
                    for k in range(int(a, 16), int(z, 16) + 1):
                        out[k][chr(int(b, 16) + k - int(a, 16))] += 1
    bad = {g: c for g, c in out.items() if len(c) > 1}
    if bad:
        raise ValueError(f"ToUnicode противоречит сам себе: {bad}")
    return {g: c.most_common(1)[0][0] for g, c in out.items()}


def tounicode_cmap(table: dict[int, str]) -> bytes:
    items = sorted(table.items())
    out = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
           "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
           "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
           "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange"]
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        out.append(f"{len(chunk)} beginbfchar")
        out += [f"<{g:04X}> <{''.join(f'{ord(c):04X}' for c in s)}>" for g, s in chunk]
        out.append("endbfchar")
    out += ["endcmap", "CMapName currentdict /CIDFont defineresource pop", "end", "end"]
    return "\n".join(out).encode()


def repair_tounicode(doc, family: str, table: dict[int, str]):
    """Копия PDF в памяти, где у всех вложенных частей шрифта полная таблица «номер рисунка → знак».
    Сам файл PDF не меняется. Возвращает новый документ и число исправленных частей шрифта."""
    import pymupdf
    data = tounicode_cmap(table)
    seen = set()
    for page in doc:
        for f in page.get_fonts(full=True):
            xref, _, typ, name = f[:4]
            if xref in seen or typ != "Type0" or family not in name:
                continue
            seen.add(xref)
            tu = doc.xref_get_key(xref, "ToUnicode")
            if tu[0] == "xref":
                doc.update_stream(int(tu[1].split()[0]), data)
            else:
                nx = doc.get_new_xref()
                doc.update_object(nx, "<<>>")
                doc.update_stream(nx, data)
                doc.xref_set_key(xref, "ToUnicode", f"{nx} 0 R")
    return pymupdf.open("pdf", doc.tobytes()), len(seen)


def broken_chars(doc, family: str) -> Counter:
    """Сколько знаков каждого номера рисунка не имеют таблицы (PyMuPDF отдаёт вместо них номер)."""
    c = Counter()
    for page in doc:
        for sp in page.get_texttrace():
            if family in sp["font"]:
                c.update(ch[1] for ch in sp["chars"] if ch[0] == 0xFFFD)
    return c


# ---------- 2. переносы ----------
def mark_normalize(t: str) -> str:
    """normalize() из parse.py, но с отметками в местах, где он склеил слово или где был мягкий перенос."""
    # «-\u00ad\n»: normalize() сначала убирает мягкий перенос и склеивает «-\n», значит это не мягкий перенос
    t = re.sub("(?<!-)\u00ad(?=[ \t]*\n)", M_SOFT, t)
    t = t.replace("­", "")
    t = t.replace(" ", " ")
    t = re.sub(r"(?<=[^\W\d_])-\n(?=[^\W\d_])", M_JOIN, t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


K3 = re.compile(rf"(?<=[{LETTER}])([{HY}])([ \t]*\n[ \t]*)(?=[{LETTER}])")


def breaks_in(marked: str) -> tuple[str, list[dict]]:
    """Убирает отметки, возвращает (текст как v2, список переносов с позициями в нём)."""
    base, found, removed = [], [], 0
    for i, ch in enumerate(marked):
        if ch == M_JOIN:
            found.append({"pos": i - removed, "kind": "дефис в конце строки (v2 склеил)", "span": 0, "hy": "-"})
            removed += 1
        elif ch == M_SOFT:
            found.append({"pos": i - removed, "kind": "мягкий перенос", "span": None, "hy": ""})
            removed += 1
        else:
            base.append(ch)
    base = "".join(base)
    for f in found:
        if f["span"] is None:
            m = re.match(r"[ \t]*\n[ \t]*", base[f["pos"]:])
            f["span"] = len(m.group(0)) if m else 0
    for m in K3.finditer(base):
        kind = "неразрывный дефис в конце строки" if m.group(1) != "-" else "дефис с пробелом в конце строки"
        found.append({"pos": m.start(), "kind": kind, "span": len(m.group(0)), "hy": m.group(1)})
    for f in found:
        left = re.search(rf"[{LETTER}]+$", base[:f["pos"]])
        right = re.match(rf"[{LETTER}]+", base[f["pos"] + f["span"]:])
        f["left"] = left.group(0) if left else ""
        f["right"] = right.group(0) if right else ""
    found = [f for f in found if f["left"] and f["right"]]
    found.sort(key=lambda f: f["pos"])
    return base, found


class Forms:
    """Как слова написаны внутри строки (где переноса нет) — по всем отчётам и по каждому."""

    def __init__(self):
        self.pair = defaultdict(Counter)     # ("социально","экономическое") -> {отчёт: раз}
        self.word = defaultdict(Counter)     # "водоснабжение" -> {отчёт: раз}

    def add(self, rid: str, raw: str) -> None:
        raw = raw.replace(" ", " ")
        lines = raw.split("\n")
        cont = False
        for ln in lines:
            toks = list(TOKEN.finditer(ln.replace("­", "­")))
            ends_broken = bool(re.search(rf"[{LETTER}](?:[{HY}][ \t]*|­[ \t]*)$", ln))
            for i, m in enumerate(toks):
                if i == 0 and cont and m.start() == len(ln) - len(ln.lstrip()):
                    continue
                if i == len(toks) - 1 and ends_broken:
                    continue
                parts = re.split(f"[{HY}]", m.group(0).lower())
                if "­" in ln[m.start():m.end() + 1]:
                    continue
                for p in parts:
                    self.word[p][rid] += 1
                for a, b in zip(parts, parts[1:]):
                    self.pair[(a, b)][rid] += 1
            cont = ends_broken

    def freeze(self) -> None:
        self.words_sorted = sorted(self.word)
        self.pair_stem = defaultdict(Counter)
        for (a, b), c in self.pair.items():
            for k in (4,):
                self.pair_stem[(a, b[:k])].update(c)

    def inside(self, w: str) -> bool:
        """«природнадзора» есть внутри «Росприроднадзора»: слово так пишется слитно."""
        if not hasattr(self, "_blob"):
            self._blob = "\n".join(self.words_sorted)
        return any(len(x) > len(w) for x in re.findall(rf"[^\n]*{re.escape(w)}[^\n]*", self._blob))

    def known(self, w: str) -> bool:
        """Слово встречается в PDF внутри строки (само по себе, не как часть другого)."""
        return sum(self.word[w].values()) > 0

    def word_prefix(self, prefix: str, rid: str | None) -> int:
        i = bisect.bisect_left(self.words_sorted, prefix)
        n = 0
        while i < len(self.words_sorted) and self.words_sorted[i].startswith(prefix):
            c = self.word[self.words_sorted[i]]
            n += c[rid] if rid else sum(c.values())
            i += 1
        return n


def decide(f: dict, rid: str, forms: Forms) -> tuple[str, str, int, int]:
    a, b = f["left"], f["right"]
    al, bl = a.lower(), b.lower()
    if f["kind"] == "мягкий перенос":
        return "слитно", "мягкий перенос в PDF — это всегда перенос внутри слова", 0, 0
    for scope, r in (("в этом отчёте", rid), ("во всех отчётах", None)):
        h = forms.pair[(al, bl)][r] if r else sum(forms.pair[(al, bl)].values())
        g = forms.word[al + bl][r] if r else sum(forms.word[al + bl].values())
        if h or g:
            if h > g:
                return "через дефис", f"PDF {scope}: внутри строки через дефис {h} раз, слитно {g}", h, g
            if g > h:
                return "слитно", f"PDF {scope}: внутри строки слитно {g} раз, через дефис {h}", h, g
    if len(bl) >= 5:
        for scope, r in (("в этом отчёте", rid), ("во всех отчётах", None)):
            st = bl[:4]
            h = forms.pair_stem[(al, st)][r] if r else sum(forms.pair_stem[(al, st)].values())
            g = forms.word_prefix(al + st, r)
            if h or g:
                if h > g:
                    return "через дефис", f"PDF {scope}: однокоренные внутри строки через дефис {h}, слитно {g}", h, g
                if g > h:
                    return "слитно", f"PDF {scope}: однокоренные внутри строки слитно {g}, через дефис {h}", h, g
    if bl in SUSPENDED and b == bl and al[-1:] in "оеи" and len(al) >= 4:
        return "висячий дефис", f"в PDF слитного «{al + bl}» нет; после дефиса «{b}»: «{a}- {b} …»", 0, 0
    if b[:1].isupper() and not a.isupper():
        # сверка 16.11: почти всегда это не перенос слова, а следующая строка из другой колонки или заголовок
        # («уча-» + «Цепочка поставок»). Ни склеивать, ни ставить дефис нельзя — оставляем как в PDF.
        return "перенос строки", "в PDF нет; дальше слово с заглавной (обычно другая колонка) — оставлено как в PDF", 0, 0
    if a.isupper() and b.isupper() and len(b) >= 2 and forms.known(bl) and forms.known(al) and min(len(al), len(bl)) >= 4:
        return "через дефис", "в PDF нет; обе части — отдельные слова, написанные прописными", 0, 0
    if al in PREFIX_OK:
        return "через дефис", f"в PDF нет; «{al}-» — первая часть составного слова", 0, 0
    if re.search("[a-z]", al) and re.search("[а-яё]", bl):
        return "через дефис", "в PDF нет; латиница + кириллица («IT-разработчиков»)", 0, 0
    if forms.inside(al + bl):
        return "слитно", f"в PDF «{al + bl}» встречается внутри более длинного слова", 0, 0
    if al in GLUED_FIRST:
        return "слитно", f"в PDF нет; с «{al}» слова пишутся слитно", 0, 0
    if (min(len(al), len(bl)) >= 5 and forms.known(al) and forms.known(bl)
            and not bl.startswith(TAILS)):
        return "через дефис", "в PDF нет; обе части — отдельные слова («семинаре-совещании»)", 0, 0
    if al.endswith(("но", "ко", "во", "ро", "то", "мо", "по")) and len(al) >= 4 and len(bl) >= 6 and forms.known(bl) and not bl.startswith(TAILS):
        return "через дефис", "в PDF нет; «…о-» плюс отдельное слово («кабельно-проводниковой»)", 0, 0
    return "слитно", "в PDF нет; обычный перенос слова", 0, 0


# ---------- главное ----------
def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    import pymupdf
    pdf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "reports"
    if (OUT / "переносы.csv").exists():
        sys.exit("data/text_v4/переносы.csv уже есть: готовые файлы не перезаписываем.")
    OUT.mkdir(parents=True, exist_ok=True)
    rids = sorted(p.stem for p in V2.glob("*.jsonl"))
    raw_pages: dict[str, list[tuple[int, str]]] = {}
    sources = []
    font_log = Counter()
    table_rows = []
    for rid in rids:
        v2 = [json.loads(l) for l in open(V2 / f"{rid}.jsonl", encoding="utf-8")]
        if rid in TXT_REPORTS:
            txt = ROOT / "data" / "reports" / f"{rid}.txt"
            raw_pages[rid] = split_pages_txt(txt.read_text(encoding="utf-8"))
            sources.append({"report_id": rid, "файл": txt.name, "sha256": sha(txt), "проверка": "текст из .txt, PDF нет"})
            continue
        pdf = pdf_dir / f"{rid}.pdf"
        doc = pymupdf.open(pdf)
        if len(doc) != len(v2):
            raise SystemExit(f"{rid}: в PDF {len(doc)} стр., в v2 {len(v2)}")
        pages = []
        if rid in BROKEN_FONT:
            fam = BROKEN_FONT[rid]
            tu = tounicode_table(doc, fam)
            rule = hoves_rule()
            # лигатуры: в ToUnicode «ﬃ», в правиле «ffi» — это одно и то же (NFKC)
            conflicts = {g: (c, rule.get(g)) for g, c in tu.items()
                         if g in rule and unicodedata.normalize("NFKC", rule[g]) != unicodedata.normalize("NFKC", c)}
            if conflicts:
                raise SystemExit(f"{rid}: правило шрифта расходится с ToUnicode: {conflicts}")
            table = {**tu, **rule}   # правило пишет лигатуры буквами («ffi»), чтобы слово находилось поиском
            need = broken_chars(doc, fam)
            unknown = {g: n for g, n in need.items() if g not in table}
            if unknown:
                raise SystemExit(f"{rid}: не опознаны номера рисунков {unknown}")
            fixed, nfonts = repair_tounicode(doc, fam, table)
            if broken_chars(fixed, fam):
                raise SystemExit(f"{rid}: после починки остались знаки без таблицы")
            same = 0
            for i, page in enumerate(fixed):
                t = page.get_text("text")
                if normalize(t) == v2[i]["text"]:
                    same += 1
                pages.append((i + 1, t))
            # страницы, где в v2 не было ни одного знака без таблицы, должны совпасть с v2 символ в символ
            clean_pages = [i for i, page in enumerate(doc)
                           if not any(ch[0] == 0xFFFD for sp in page.get_texttrace() if fam in sp["font"]
                                      for ch in sp["chars"])]
            for i in clean_pages:
                nf = lambda x: unicodedata.normalize("NFKC", x)   # лигатура «ﬃ» теперь пишется «ffi»
                if nf(normalize(pages[i][1])) != nf(v2[i]["text"]):
                    raise SystemExit(f"{rid} стр. {i + 1}: страница без сломанных знаков изменилась")
            for g in sorted(need):
                src = ("ToUnicode других частей этого же шрифта" if g in tu else
                       "картинка страницы (правило шрифта)" if g in SEEN_ON_IMAGE else "правило шрифта")
                font_log[g] = need[g]
                table_rows.append({"номер_рисунка": g, "было_в_v2": chr(g) if g > 31 else f"\\x{g:02x}",
                                   "знак": table[g], "откуда_известно": src, "раз": need[g]})
            print(f"{rid}: шрифт починен в {nfonts} частях, знаков {sum(need.values())}, "
                  f"страниц без изменений {same} из {len(pages)}", flush=True)
            with open(OUT / f"база_{rid}.jsonl", "x", encoding="utf-8", newline="\n") as fh:
                for p, t in pages:
                    t2 = normalize(t)
                    fh.write(json.dumps({"report_id": rid, "page": p, "text": t2, "n_chars": len(t2.strip())},
                                        ensure_ascii=False) + "\n")
        else:
            for i, page in enumerate(doc):
                t = page.get_text("text")
                if normalize(t) != v2[i]["text"]:
                    raise SystemExit(f"{rid} стр. {i + 1}: разбор не совпал с data/pages — другая версия PyMuPDF?")
                pages.append((i + 1, t))
        raw_pages[rid] = pages
        sources.append({"report_id": rid, "файл": pdf.name, "sha256": sha(pdf),
                        "проверка": f"PyMuPDF {pymupdf.VersionBind}: разбор совпал с data/pages (v2) на всех страницах"})
        print(rid, len(pages), "стр.", flush=True)

    forms = Forms()
    for rid, pages in raw_pages.items():
        for _, t in pages:
            forms.add(rid, t)
    forms.freeze()

    rows = []
    stat = Counter()
    for rid, pages in raw_pages.items():
        for p, t in pages:
            base, found = breaks_in(mark_normalize(t))
            if base != normalize(t):   # позиции переносов должны относиться ровно к тексту v2
                raise SystemExit(f"{rid} стр. {p}: текст с отметками переносов не совпал с normalize()")
            for f in found:
                dec, why, h, g = decide(f, rid, forms)
                stat[(f["kind"], dec)] += 1
                rows.append({"report_id": rid, "page": p, "позиция": f["pos"], "длина": f["span"], "вид": f["kind"],
                             "дефис": f["hy"], "слева": f["left"], "справа": f["right"], "решение": dec,
                             "довод": why, "в_PDF_через_дефис": h, "в_PDF_слитно": g})
    write_csv(OUT / "переносы.csv", rows, ["report_id", "page", "позиция", "длина", "вид", "дефис", "слева", "справа",
                                           "решение", "довод", "в_PDF_через_дефис", "в_PDF_слитно"])
    write_csv(OUT / "шрифт_MAGN-2025_таблица.csv", table_rows,
              ["номер_рисунка", "было_в_v2", "знак", "откуда_известно", "раз"])
    write_csv(OUT / "pdf_источники.csv", sources, ["report_id", "файл", "sha256", "проверка"])
    for k, v in sorted(stat.items()):
        print(k, v)
    print("ММК 2025: знаков без таблицы исправлено", sum(font_log.values()))


if __name__ == "__main__":
    main()
