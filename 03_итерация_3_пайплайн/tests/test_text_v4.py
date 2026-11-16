"""Проверки текстов v4: ловят ошибки, найденные проверкой 16.11.2026, чтобы они не вернулись.

    python -m unittest tests.test_text_v4 -v          (PDF не нужны)

Классы ошибок:
  1. ММК 2025: битый шрифт («№» → 9, сдвинутая латиница, значки вместо букв).
  2. Дефисы: ставить только там, где так в самом PDF; не склеивать «энерго- и»; мягкие переносы склеены.
  3. Скрипты берут тексты по версии (src/text_versions.py), замороженное извлечение v1 — на v2.
  4. Версия PyMuPDF закреплена на существующей и проверенной.
  5. Цитаты заявлений и эталона стоят на странице v4 дословно, буквы те же, что в v2.
"""
import csv
import json
import re
import sys
import unicodedata
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import text_versions as tv  # noqa: E402
from parse import normalize  # noqa: E402

V4 = ROOT / "data" / "pages_v4"
REP = ROOT / "data" / "text_v4"
HAVE_V4 = V4.exists() and any(V4.glob("*.jsonl"))


def pages(d: Path, rid: str) -> dict[int, str]:
    with open(d / f"{rid}.jsonl", encoding="utf-8") as f:
        return {int(r["page"]): r["text"] for r in map(json.loads, f)}


def flat(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def read_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def letters(s: str) -> str:
    return "".join(ch.lower().replace("ё", "е") for ch in s if ch.isalnum())


class MarkNormalizeTests(unittest.TestCase):
    """Отметки переносов не должны менять текст: позиции относятся ровно к normalize() (v2)."""

    @classmethod
    def setUpClass(cls):
        try:
            import pdf_evidence_v4 as ev
        except ImportError as e:   # нет pymupdf
            raise unittest.SkipTest(str(e))
        cls.ev = ev

    def check(self, raw):
        base, found = self.ev.breaks_in(self.ev.mark_normalize(raw))
        self.assertEqual(base, normalize(raw))
        return found

    def test_hyphen_then_soft_hyphen_is_plain_hyphen_break(self):
        # AKRN-2023 стр. 4: «социально-­\nэкономическое» — ошибка, найденная при сборке v4
        found = self.check("на социально-­\nэкономическое развитие")
        self.assertEqual([(f["left"], f["right"], f["kind"]) for f in found],
                         [("социально", "экономическое", "дефис в конце строки (v2 склеил)")])

    def test_soft_hyphen_break(self):
        found = self.check("действу­\nющий порядок")
        self.assertEqual([(f["left"], f["right"], f["kind"]) for f in found],
                         [("действу", "ющий", "мягкий перенос")])

    def test_soft_hyphen_inside_line_and_nbsp(self):
        self.assertEqual(self.check("эко­логия и вода\n\n\n\nконец"), [])

    def test_hyphen_with_space_before_newline(self):
        found = self.check("энерго- \nи ресурсосбережение")
        self.assertEqual([(f["left"], f["right"], f["span"]) for f in found], [("энерго", "и", 3)])

    def test_decide_follows_pdf_not_dictionary(self):
        ev = self.ev
        forms = ev.Forms()
        forms.add("X", "рискориентированного подхода\nрискориентированного\n")
        forms.add("Y", "социально-экономическое развитие\n")
        forms.freeze()
        brk = {"kind": "дефис в конце строки (v2 склеил)"}
        self.assertEqual(ev.decide(dict(brk, left="риск", right="ориентированного"), "X", forms)[0], "слитно")
        self.assertEqual(ev.decide(dict(brk, left="социально", right="экономическое"), "X", forms)[0],
                         "через дефис")
        self.assertEqual(ev.decide(dict(brk, left="энерго", right="и"), "X", forms)[0], "висячий дефис")
        self.assertEqual(ev.decide({"kind": "мягкий перенос", "left": "Мос", "right": "Энерго"}, "X", forms)[0],
                         "слитно")
        # «уча-» + «Цепочка поставок» из другой колонки: не клеить и не ставить дефис, оставить как в PDF
        self.assertEqual(ev.decide(dict(brk, left="уча", right="Цепочка"), "X", forms)[0], "перенос строки")


class ApplyBreaksTests(unittest.TestCase):
    def test_wrong_position_is_refused(self):
        from clean_text_v4 import apply_breaks
        row = {"позиция": "5", "длина": "1", "слева": "энерго", "справа": "и", "дефис": "-", "решение": "слитно"}
        with self.assertRaises(SystemExit):
            apply_breaks("энерго\nи", [row], "тест")

    def test_decisions(self):
        from clean_text_v4 import apply_breaks
        t = "энерго- \nи ресурсо\nсбережение"
        rows = [{"позиция": "6", "длина": "3", "слева": "энерго", "справа": "и", "дефис": "-",
                 "решение": "висячий дефис"},
                {"позиция": "18", "длина": "1", "слева": "ресурсо", "справа": "сбережение", "дефис": "",
                 "решение": "слитно"}]
        self.assertEqual(apply_breaks(t, rows, "тест"), "энерго- и ресурсосбережение")

    def test_word_broken_twice(self):
        # RUAL-2025 стр. 114: «промышленно-\nтехнологический» внутри правой части другого переноса
        from clean_text_v4 import apply_breaks
        t = "Тайшетскийпромышленнотехнологический"   # так в v2: оба «-\n» склеены
        rows = [{"позиция": "10", "длина": "0", "слева": "Тайшетский", "справа": "промышленнотехнологический",
                 "дефис": "-", "решение": "через дефис"},
                {"позиция": "21", "длина": "0", "слева": "Тайшетскийпромышленно", "справа": "технологический",
                 "дефис": "-", "решение": "через дефис"}]
        self.assertEqual(apply_breaks(t, rows, "тест"), "Тайшетский-промышленно-технологический")


class VersionTests(unittest.TestCase):
    def test_current_is_v4_and_frozen_extract_on_v2(self):
        self.assertEqual(tv.CURRENT, "v4")
        self.assertEqual(tv.FROZEN_EXTRACT_V1, "v2")
        self.assertEqual(tv.pages_dir("v2"), ROOT / "data/pages")
        self.assertEqual(tv.gold_csv(), ROOT / "data/out/gold_extract_text_v4.csv")
        with self.assertRaises(ValueError):
            tv.pages_dir("v9")

    def test_no_script_hardcodes_text_folders(self):
        """Тексты выбираются через text_versions; жёсткий путь — только в скриптах, создающих версию."""
        allowed = {"text_versions.py", "parse.py", "clean_text_v3.py", "clean_text_v4.py", "pdf_evidence_v4.py",
                   "migrate_to_v3.py", "affected_v3.py", "migrate_to_v4.py",
                   "parse_txt.py", "check_v4_pdf.py"}   # создают версию или сверяют версии между собой
        pat = re.compile(r"""['"/]data/(pages|chunks)['"/]|['"]data['"]\s*/\s*['"](pages|chunks)['"]""")
        bad = [p.name for p in (ROOT / "src").glob("*.py") if p.name not in allowed and pat.search(p.read_text("utf-8"))]
        self.assertEqual(bad, [], "скрипты с жёстким путём к data/pages или data/chunks")

    def test_pymupdf_pinned_to_real_checked_version(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(req, r"(?m)^pymupdf==1\.28\.2\b")
        self.assertNotIn("1.28.6", req.split("#")[0])
        src = read_csv(REP / "pdf_источники.csv") if (REP / "pdf_источники.csv").exists() else []
        for r in src:
            if r["проверка"].startswith("PyMuPDF"):
                self.assertIn("1.28.2", r["проверка"])


@unittest.skipUnless(HAVE_V4, "нет data/pages_v4")
class TextV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rids = sorted(p.stem for p in (ROOT / "data/pages").glob("*.jsonl"))

    def test_all_reports_and_pages(self):
        self.assertEqual(sorted(p.stem for p in V4.glob("*.jsonl")), self.rids)
        self.assertEqual(len(self.rids), 92)   # 90 PDF + 2 текста Мосводоканала
        for rid in self.rids:   # Мосводоканал: страницы по печатным номерам, как в v3
            ref = ROOT / ("data/pages_v3" if rid.startswith("MVDK") else "data/pages")
            self.assertEqual(len(pages(V4, rid)), len(pages(ref, rid)), rid)

    def test_magn_2025_font_repaired(self):
        p = pages(V4, "MAGN-2025-ИО")
        allp = "\n".join(p.values())
        # значки битого шрифта (рисунки без таблицы) — их не должно остаться
        # в v2 тут было 13 тыс. таких знаков: номер рисунка шрифта вместо буквы
        bad = [ch for ch in allp if 0x300 <= ord(ch) <= 0x36F or 0x500 <= ord(ch) <= 0x6FF
               or 0xE000 <= ord(ch) <= 0xF8FF or ch == "\ufffd"]
        self.assertEqual(Counter(bad).most_common(5), [])
        p108 = flat(p[108])
        for s in ("№ 12", "лауреата V", "III–IV"):
            self.assertIn(s, p108)
        self.assertIn("GRI", allp)
        self.assertNotIn("JUL", allp)    # «GRI» со сдвигом латиницы
        v3 = " ".join(pages(ROOT / "data/pages_v3", "MAGN-2025-ИО").values())
        self.assertGreater(allp.count("№"), v3.count("№") + 20, "«№» потерян, как в v3")
        self.assertIsNone(re.search(r"(?<!№ )(?<!№)(?<![\d.,])9 ?\d+-ФЗ", allp), "«№» превратился в 9 перед номером закона")
        cyr = sum(1 for ch in allp if "а" <= ch.lower() <= "я")
        self.assertGreater(cyr / max(1, sum(ch.isalpha() for ch in allp)), 0.8)

    def test_hyphens_follow_pdf(self):
        cases = [("URKA-2025-ГО", 21, "рискориентированного", "риск-ориентированного"),
                 ("RVDK-2025-ОУР", 16, "Новосакмарского", "Ново-сакмарского"),
                 ("AKRN-2023-ОУР", 4, "социально-экономическое", "социальноэкономическое")]
        for rid, pg, good, bad in cases:
            t = flat(pages(V4, rid)[pg])
            self.assertTrue(good in t, f"{rid} стр. {pg}: нет «{good}»")
            self.assertFalse(bad in t, f"{rid} стр. {pg}: есть «{bad}»")
        self.assertTrue("нитрит-нитрат" in flat(" ".join(pages(V4, "URCH-2024-ОУР").values())))
        # в одном отчёте PDF пишет «аудиосказок», в другом «аудио-сказок» — v4 повторяет каждый PDF
        self.assertTrue("аудиосказок" in flat(" ".join(pages(V4, "RVDK-2025-ОУР").values())))
        self.assertTrue("аудио-сказок" in flat(" ".join(pages(V4, "RVDK-2024-ОУР").values())))
        allt = " ".join(flat(t) for rid in self.rids for t in pages(V4, rid).values())
        self.assertFalse("энергои ресурсо" in allt, "висячий дефис склеен")

    def test_no_new_hyphen_without_reason(self):
        """Каждый дефис v4, которого нет в v2, — это перенос из переносы.csv с решением «через дефис»."""
        rows = read_csv(REP / "переносы.csv")
        hy = Counter(r["report_id"] for r in rows if r["решение"] != "слитно")
        pat = re.compile(r"[^\W\d_][-‐‑] ?[^\W\d_]")
        for rid in self.rids:
            if rid == "MAGN-2025-ИО" or rid.startswith("MVDK"):
                continue
            n2 = sum(len(pat.findall(t)) for t in pages(ROOT / "data/pages", rid).values())
            n4 = sum(len(pat.findall(t)) for t in pages(V4, rid).values())
            self.assertLessEqual(n4 - n2, hy[rid], rid)

    def test_no_soft_hyphen_or_v2_glue_left(self):
        rows = read_csv(REP / "переносы.csv")
        dec = Counter(r["решение"] for r in rows)
        self.assertEqual(set(dec) - {"слитно", "через дефис", "висячий дефис", "перенос строки"}, set())
        self.assertTrue(all(r["довод"] for r in rows))
        for rid in self.rids:
            for pg, t in pages(V4, rid).items():
                self.assertNotIn("­", t)
        soft = [r for r in rows if r["вид"] == "мягкий перенос"]
        self.assertGreater(len(soft), 10000)
        self.assertTrue(all(r["решение"] == "слитно" for r in soft))

    def test_evidence_decisions_agree_with_pdf_counts(self):
        """Где в PDF есть само слово, решение совпадает с большинством написаний в PDF."""
        for r in read_csv(REP / "переносы.csv"):
            h, g = int(r["в_PDF_через_дефис"] or 0), int(r["в_PDF_слитно"] or 0)
            if r["довод"].startswith("PDF в этом отчёте: внутри строки"):
                self.assertEqual(r["решение"], "через дефис" if h > g else "слитно", r)

    def test_letters_conserved_except_headers(self):
        """v4 не теряет и не добавляет буквы по сравнению с v2 (кроме убранных колонтитулов и ММК 2025)."""
        heads = {}
        for r in read_csv(REP / "колонтитулы.csv"):
            heads.setdefault(r["report_id"], []).append(letters(r["строка"]))
        for rid in self.rids:
            if rid == "MAGN-2025-ИО" or rid.startswith("MVDK"):
                continue
            v2, v4 = pages(ROOT / "data/pages", rid), pages(V4, rid)
            for pg in v2:
                a, b = letters(v2[pg]), letters(v4[pg])
                if a == b:
                    continue
                for h in sorted(heads.get(rid, []), key=len, reverse=True):
                    a = a.replace(h, "")
                    b = b.replace(h, "")
                self.assertEqual(a, b, f"{rid} стр. {pg}")

    def test_quality_table(self):
        q = {r["report_id"]: r for r in read_csv(V4 / "quality.csv")}
        self.assertEqual(sorted(q), self.rids)
        self.assertEqual(q["TRMK-2023-ИО"]["verdict"], "проверить")


@unittest.skipUnless((ROOT / "data/out/claims_text_v4.csv").exists(), "нет claims_text_v4.csv")
class QuotesV4Tests(unittest.TestCase):
    def check(self, path, idcol, textcol, n):
        rows = read_csv(path)
        self.assertEqual(len(rows), n)
        bad = []
        for r in rows:
            if r["check_v4"] != "есть на странице v4":
                continue
            t = flat(pages(V4, r["report_id"])[int(r["page"])])
            if flat(r[textcol]).strip() not in t:
                bad.append(r[idcol])
        self.assertEqual(bad, [])
        return rows

    def test_claims(self):
        rows = self.check(ROOT / "data/out/claims_text_v4.csv", "claim_id", "text",
                          len(read_csv(ROOT / "data/out/claims.csv")))
        unresolved = [r for r in rows if r["check_v4"] != "есть на странице v4"]
        self.assertLessEqual(len(unresolved), 5)

    def test_gold(self):
        rows = self.check(ROOT / "data/out/gold_extract_text_v4.csv", "sentence_id", "sentence",
                          len(read_csv(ROOT / "data/out/gold_extract.csv")))
        old = {r["sentence_id"]: r for r in read_csv(ROOT / "data/out/gold_extract.csv")}
        for r in rows:   # метки не тронуты
            for k in ("final_is_claim", "final_type", "final_esg_block", "final_topic"):
                if k in r:
                    self.assertEqual(r[k], old[r["sentence_id"]][k])


if __name__ == "__main__":
    unittest.main()
