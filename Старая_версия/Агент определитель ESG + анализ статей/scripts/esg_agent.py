"""Агент-определитель ESG: механика без модели.

Модель (Claude в потоке проекта) только читает действующий промпт agent/esg_agent_v2.md и партию,
а пишет ответ в llm/esg_<версия>/<партия>.json (проверка на эталоне — llm/eval_<версия>/). Всё остальное делает этот скрипт:

  prepare   любой отчёт (PDF, TXT, JSONL страниц проекта) -> предложения -> партии
  make-eval партии для проверки агента на эталоне проекта (gold_extract_text_v4.csv)
  check     проверка ответа модели: формат, значения, полнота
  evaluate  сравнение ответов с эталоном: точность, каппа, матрица ошибок, список ошибок
  export    сборка таблицы ESG-заявлений отчёта (CSV ; UTF-8 с BOM) и сводки E/S/G
  manifest  строка журнала партии (sha256 входа и промпта)

Примеры (из корня репозитория):
  python "Агент определитель ESG + анализ статей/scripts/esg_agent.py" prepare отчёт.pdf --report-id ABCD-2024-ОУР
  python ".../esg_agent.py" check work/ABCD-2024-ОУР/batches/ABCD-2024-ОУР_b001.jsonl llm/esg_v2/ABCD-2024-ОУР_b001.json
  python ".../esg_agent.py" export ABCD-2024-ОУР --version v2

Только стандартная библиотека; для PDF нужен pymupdf (как в requirements.txt проекта).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]          # папка «Агент определитель ESG + анализ статей»
REPO = AGENT.parent
PIPE = REPO / "03_итерация_3_пайплайн"
GOLD = PIPE / "data" / "out" / "gold_extract_text_v4.csv"
PROMPT = AGENT / "agent" / "esg_agent_v2.md"  # действующая версия промпта
TAXONOMY = AGENT / "agent" / "taxonomy.csv"

BLOCKS = ("E", "S", "G")
YESNO = ("да", "нет")
CONF = ("высокая", "средняя", "низкая")
FIELDS = ("sentence_id", "is_esg", "block", "topic", "block2", "confidence", "rule", "essence", "reason")
_RULE = r"(Н[1-8]|З([1-9]|10)|Б[1-6]|Т([1-9]|1\d|2[0-4]))"
RULE_RE = re.compile(rf"^{_RULE}(\s*,\s*{_RULE})*$")
SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[«\"(A-ZА-ЯЁ0-9•])")
BATCH_SIZE = 40


# ---------------------------------------------------------------- общие функции
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def taxonomy() -> dict[str, set[str]]:
    topics: dict[str, set[str]] = defaultdict(set)
    for r in read_csv(TAXONOMY):
        topics[r["block"]].add(r["topic"])
    return topics


# ---------------------------------------------------------------- 1. любой отчёт -> страницы
def load_pages(src: Path) -> list[tuple[int, str]]:
    """Страницы отчёта: [(номер страницы, текст)].

    PDF — номер страницы PDF, текст через pymupdf без sort=True (sort смешивает колонки,
    см. кодбук проекта). TXT — разрыв страницы \\f или строка «=== стр. N ===», иначе весь
    файл одна страница. JSONL — формат проекта data/pages_v4: {"page": N, "text": ...}.
    """
    suf = src.suffix.lower()
    if suf == ".pdf":
        try:
            import pymupdf  # type: ignore
        except ImportError:  # старые версии
            import fitz as pymupdf  # type: ignore
        doc = pymupdf.open(src)
        return [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    if suf == ".jsonl":
        return [(int(d["page"]), d.get("text", "")) for d in read_jsonl(src)]
    text = src.read_text(encoding="utf-8", errors="replace")
    marks = list(re.finditer(r"^=+\s*стр\.?\s*(\d+)\s*=+\s*$", text, flags=re.M))
    if marks:
        out = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            out.append((int(m.group(1)), text[m.end():end]))
        return out
    if "\f" in text:
        return [(i + 1, t) for i, t in enumerate(text.split("\f"))]
    return [(1, text)]


def clean(text: str) -> str:
    text = text.replace("­", "")                      # мягкий перенос
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)           # перенос слова по строке
    text = re.sub(r"[ \t   ]+", " ", text)
    return text


ABBR_END = re.compile(r"(?:^|[\s(«])(?:тыс|млн|млрд|трлн|см|рис|табл|прил|им|ул|т\.\s?е|т\.\s?к|т\.\s?п|т\.\s?д|др)\.$", re.IGNORECASE)
PAGE_REF_END = re.compile(r"(?:^|[\s(«])(?:с|стр|п|пп|гл|разд)\.$", re.IGNORECASE)


def split_sentences(page_text: str) -> list[str]:
    out = []
    for para in re.split(r"\n\s*\n", clean(page_text)):
        para = re.sub(r"\s*\n\s*", " ", para).strip()
        if not para:
            continue
        parts = [s.strip() for s in SENT_SPLIT.split(para) if s.strip()]
        for s in parts:
            # не резать после сокращений: «36,5 тыс.» + «МВт·ч …», «с.» + «45», «см.» + «Приложение»
            if out and (ABBR_END.search(out[-1]) or (PAGE_REF_END.search(out[-1]) and s[:1].isdigit())):
                out[-1] = out[-1] + " " + s
            else:
                out.append(s)
    return out


def is_noise(s: str) -> bool:
    """Строки, которые никогда не бывают заявлением: очень короткие, без букв, таблицы из чисел."""
    letters = sum(ch.isalpha() for ch in s)
    if len(s) < 25 or letters < 15:
        return True
    digits = sum(ch.isdigit() for ch in s)
    return digits > letters  # строка таблицы


def esg_stems() -> list[str]:
    stems = set()
    for r in read_csv(TAXONOMY):
        for c in r["слова-признаки (начала слов)"].split("|"):
            c = c.strip().lower()
            if len(c) >= 3:
                stems.add(c.split()[0])
    stems |= {"esg", "устойчив", "ответствен", "социальн", "персонал", "сотрудник", "работник",
              "компани", "политик", "цел", "стратеги", "снижен", "сокращ", "эколог", "здоров",
              "ohsas", "iso", "намерен", "стремим", "стремится", "безопасн", "качеств"}
    return sorted(stems)


def has_esg_word(s: str, stems: list[str]) -> bool:
    low = s.lower()
    return any(st in low for st in stems)


def parse_pages(spec: str) -> set[int]:
    """«5-7,12» -> {5, 6, 7, 12}."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        elif part:
            out.add(int(part))
    return out


def cmd_prepare(a: argparse.Namespace) -> None:
    src = Path(a.source)
    rid = a.report_id or src.stem
    pages = load_pages(src)
    if a.pages:
        keep = parse_pages(a.pages)
        pages = [(n, t) for n, t in pages if n in keep]
    stems = esg_stems() if a.esg_filter else []
    rows, dropped = [], Counter()
    for page, text in pages:
        sents = split_sentences(text)
        for i, s in enumerate(sents):
            if is_noise(s):
                dropped["шум"] += 1
                continue
            if stems and not has_esg_word(s, stems):
                dropped["нет ESG-слов"] += 1
                continue
            ctx = " ".join(x for x in (sents[i - 1] if i else "", s, sents[i + 1] if i + 1 < len(sents) else "") if x)
            rows.append({"sentence_id": f"{rid}_s{len(rows) + 1:05d}", "report_id": rid, "page": page,
                         "sentence": s, "context": ctx[:1200]})
    out = Path(a.out) if a.out else AGENT / "work" / rid
    write_jsonl(out / "sentences.jsonl", rows)
    n = 0
    for n, start in enumerate(range(0, len(rows), a.batch_size), 1):
        write_jsonl(out / "batches" / f"{rid}_b{n:03d}.jsonl", rows[start:start + a.batch_size])
    print(f"{rid}: страниц {len(pages)}, предложений в работу {len(rows)}, партий {n} по ≤{a.batch_size}; "
          f"отброшено: {dict(dropped) or 0}. Папка: {out}")


# ---------------------------------------------------------------- 2. партии проверки на эталоне
def gold_rows() -> list[dict]:
    return read_csv(GOLD)


def cmd_make_eval(a: argparse.Namespace) -> None:
    rows = gold_rows()
    by_frag = defaultdict(list)
    for r in rows:
        by_frag[r["fragment_id"]].append(r)
    for frag in by_frag.values():
        frag.sort(key=lambda r: r["sentence_id"])
    split = {"working": "рабочий", "heldout": "отложенный"}[a.split]
    items = []
    for frag in by_frag.values():
        for i, r in enumerate(frag):
            if r["split"] != split:
                continue
            ctx = " ".join(x["sentence"] for x in frag[max(0, i - 1): i + 2])
            items.append({"sentence_id": r["sentence_id"], "report_id": r["report_id"], "page": int(r["page"]),
                          "sentence": r["sentence"], "context": ctx[:1200]})
    random.Random(17).shuffle(items)  # чтобы партия не шла одним отчётом и разметка не опиралась на соседей
    out = AGENT / "eval" / "batches"
    n = 0
    for n, start in enumerate(range(0, len(items), a.batch_size), 1):
        write_jsonl(out / f"{a.split}_b{n:02d}.jsonl", items[start:start + a.batch_size])
    print(f"{a.split}: {len(items)} предложений, {n} партий в {out}")


# ---------------------------------------------------------------- 3. проверка ответа
def validate(batch: list[dict], answer: list[dict]) -> list[str]:
    errs = []
    topics = taxonomy()
    ids = [b["sentence_id"] for b in batch]
    got = [x.get("sentence_id") for x in answer]
    if len(answer) != len(batch):
        errs.append(f"записей {len(answer)}, а предложений в партии {len(batch)}")
    missing = set(ids) - set(got)
    extra = set(got) - set(ids)
    if missing:
        errs.append(f"нет ответа для: {sorted(missing)[:5]}{' …' if len(missing) > 5 else ''}")
    if extra:
        errs.append(f"чужие sentence_id: {sorted(map(str, extra))[:5]}")
    dup = [k for k, v in Counter(got).items() if v > 1]
    if dup:
        errs.append(f"повторы: {dup[:5]}")
    for x in answer:
        sid = x.get("sentence_id")
        for f in FIELDS:
            if f not in x:
                errs.append(f"{sid}: нет поля {f}")
        if x.get("is_esg") not in YESNO:
            errs.append(f"{sid}: is_esg = {x.get('is_esg')!r}")
            continue
        if x.get("confidence") not in CONF:
            errs.append(f"{sid}: confidence = {x.get('confidence')!r}")
        rule = (x.get("rule") or "").strip()
        if rule and not RULE_RE.match(rule):
            errs.append(f"{sid}: rule = {rule!r} (нет такого правила)")
        if x["is_esg"] == "нет":
            for f in ("block", "topic", "block2", "essence"):
                if x.get(f):
                    errs.append(f"{sid}: is_esg = нет, но {f} заполнено")
            continue
        b = x.get("block")
        if b not in BLOCKS:
            errs.append(f"{sid}: block = {b!r}")
            continue
        if x.get("topic") not in topics[b]:
            errs.append(f"{sid}: тема {x.get('topic')!r} не из списка блока {b}")
        b2 = x.get("block2") or ""
        if b2 and (b2 not in BLOCKS or b2 == b):
            errs.append(f"{sid}: block2 = {b2!r}")
        if not (x.get("essence") or "").strip():
            errs.append(f"{sid}: пустая essence")
    return errs


def load_answer(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"{path}: ожидается JSON-массив")
    return data


def cmd_check(a: argparse.Namespace) -> None:
    errs = validate(read_jsonl(Path(a.batch)), load_answer(Path(a.answer)))
    if errs:
        print(f"ОШИБКИ ({len(errs)}):")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print("ok: формат верный, все предложения размечены")


# ---------------------------------------------------------------- 4. оценка на эталоне
def kappa(pairs: list[tuple[str, str]]) -> float:
    if not pairs:
        return float("nan")
    n = len(pairs)
    po = sum(x == y for x, y in pairs) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def collect_answers(folder: Path, prefix: str) -> dict[str, dict]:
    out = {}
    for p in sorted(folder.glob(f"{prefix}*.json")):
        for x in load_answer(p):
            out[x["sentence_id"]] = x
    return out


def cmd_evaluate(a: argparse.Namespace) -> None:
    gold = {r["sentence_id"]: r for r in gold_rows()}
    ans = collect_answers(Path(a.answers), a.prefix)
    ids = [s for s in ans if s in gold]
    if not ids:
        raise SystemExit("нет ответов, совпадающих с эталоном")
    claim_pairs = [(gold[s]["final_is_claim"], ans[s]["is_esg"]) for s in ids]
    tp = sum(g == "да" and p == "да" for g, p in claim_pairs)
    fp = sum(g == "нет" and p == "да" for g, p in claim_pairs)
    fn = sum(g == "да" and p == "нет" for g, p in claim_pairs)
    both = [s for s in ids if gold[s]["final_is_claim"] == "да" and ans[s]["is_esg"] == "да"]
    block_pairs = [(gold[s]["final_esg_block"], ans[s]["block"]) for s in both]
    topic_pairs = [(gold[s]["final_esg_block"] + ":" + gold[s]["final_topic"], ans[s]["block"] + ":" + ans[s]["topic"]) for s in both]
    conf = Counter(block_pairs)
    acc = lambda pr: sum(x == y for x, y in pr) / len(pr) if pr else float("nan")
    lines = [
        f"# Проверка агента на эталоне: {a.prefix or 'все партии'} ({Path(a.answers).name})", "",
        f"Предложений с ответом: {len(ids)} (эталон: {GOLD.relative_to(REPO)}).", "",
        "| Что сравниваем | Совпадение | Каппа Коэна | Комментарий |", "|---|---|---|---|",
        f"| ESG-заявление или нет | {acc(claim_pairs):.1%} | {kappa(claim_pairs):.2f} | точность {tp / (tp + fp):.1%}, полнота {tp / (tp + fn):.1%} |",
        f"| Буква E/S/G (где оба сказали «заявление», n={len(both)}) | {acc(block_pairs):.1%} | {kappa(block_pairs):.2f} | |",
        f"| Буква и тема | {acc(topic_pairs):.1%} | {kappa(topic_pairs):.2f} | |", "",
        "Матрица букв (строка — эталон, столбец — агент):", "",
        "| эталон \\ агент | E | S | G |", "|---|---|---|---|",
    ]
    for g in BLOCKS:
        lines.append(f"| {g} | " + " | ".join(str(conf[(g, p)]) for p in BLOCKS) + " |")
    by_conf = defaultdict(list)
    for s in both:
        by_conf[ans[s]["confidence"]].append(gold[s]["final_esg_block"] == ans[s]["block"])
    lines += ["", "Точность буквы по уверенности агента:", ""]
    for c in CONF:
        v = by_conf.get(c, [])
        if v:
            lines.append(f"- {c}: {sum(v) / len(v):.1%} из {len(v)}")
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    errs = []
    for s in ids:
        g, p = gold[s], ans[s]
        kind = ""
        if g["final_is_claim"] != p["is_esg"]:
            kind = "лишнее заявление" if p["is_esg"] == "да" else "пропущено заявление"
        elif g["final_is_claim"] == "да" and g["final_esg_block"] != p["block"]:
            kind = "буква"
        elif g["final_is_claim"] == "да" and g["final_topic"] != p["topic"]:
            kind = "тема"
        if kind:
            errs.append({"sentence_id": s, "ошибка": kind, "sentence": g["sentence"], "эталон": f"{g['final_is_claim']} {g['final_esg_block']} {g['final_topic']}".strip(),
                         "агент": f"{p['is_esg']} {p['block']} {p['topic']}".strip(), "block2": p.get("block2", ""),
                         "confidence": p["confidence"], "rule": p.get("rule", ""), "reason": p.get("reason", ""),
                         "эталон_тип": g["final_type"], "кто_решил": g["resolved_by"]})
    write_csv(Path(a.errors), errs, list(errs[0].keys()) if errs else ["sentence_id"])
    print("\n".join(lines))
    print(f"\nОшибок: {len(errs)} ({Counter(e['ошибка'] for e in errs)}). Список: {a.errors}")


# ---------------------------------------------------------------- 5. выгрузка
def cmd_export(a: argparse.Namespace) -> None:
    work = AGENT / "work" / a.report_id
    sents = {r["sentence_id"]: r for r in read_jsonl(work / "sentences.jsonl")}
    llm_dir = AGENT / "llm" / f"esg_{a.version}"  # ответы по отчётам: llm/esg_v2/
    if not llm_dir.exists():
        llm_dir = AGENT / "llm" / a.version
    ans = collect_answers(llm_dir, a.report_id)
    rows = []
    for sid, s in sents.items():
        x = ans.get(sid)
        if not x or x["is_esg"] != "да":
            continue
        rows.append({"sentence_id": sid, "report_id": s["report_id"], "page": s["page"], "block": x["block"],
                     "topic": x["topic"], "block2": x.get("block2", ""), "confidence": x["confidence"],
                     "essence": x.get("essence", ""), "sentence": s["sentence"], "reason": x.get("reason", ""),
                     "rule": x.get("rule", ""), "agent_version": a.version})
    out = work / f"{a.report_id}_esg_{a.version}.csv"
    write_csv(out, rows, list(rows[0].keys()) if rows else ["sentence_id"])
    done = sum(1 for sid in sents if sid in ans)
    cnt = Counter(r["block"] for r in rows)
    tcnt = Counter((r["block"], r["topic"]) for r in rows)
    summary = [f"# {a.report_id}: ESG-заявления по буквам (агент {a.version})", "",
               f"Размечено предложений: {done} из {len(sents)}. ESG-заявлений: {len(rows)}.", "",
               "| Буква | Заявлений | Доля |", "|---|---|---|"]
    for b in BLOCKS:
        summary.append(f"| {b} | {cnt[b]} | {cnt[b] / len(rows):.0%} |" if rows else f"| {b} | 0 | — |")
    summary += ["", "| Буква | Тема | Заявлений |", "|---|---|---|"]
    for (b, t), n in sorted(tcnt.items(), key=lambda kv: (kv[0][0], -kv[1])):
        summary.append(f"| {b} | {t} | {n} |")
    (work / f"{a.report_id}_сводка_{a.version}.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"{out} ({len(rows)} заявлений); сводка: {work / (a.report_id + '_сводка_' + a.version + '.md')}")
    if done < len(sents):
        print(f"ВНИМАНИЕ: нет ответов для {len(sents) - done} предложений — не все партии размечены")


# ---------------------------------------------------------------- 6. журнал
def cmd_manifest(a: argparse.Namespace) -> None:
    batch, answer = Path(a.batch), Path(a.answer)
    prompt = Path(a.prompt) if a.prompt else PROMPT
    n = len(read_jsonl(batch))
    errs = validate(read_jsonl(batch), load_answer(answer))
    stem = answer.stem
    rid = stem.rsplit("_b", 1)[0] if re.match(r"^[A-Z]{4}-\d{4}-", stem) else ""
    from datetime import datetime, timezone
    row = {"batch_id": f"{answer.parent.name}_{stem}", "stage": "esg_agent", "company_id": rid[:4], "report_id": rid,
           "input_file": str(batch.resolve().relative_to(REPO)), "input_sha256": sha256(batch),
           "prompt_file": str(prompt.resolve().relative_to(REPO)), "prompt_sha256": sha256(prompt),
           "model": a.model, "thread": a.thread, "started_at": a.started or "", "finished_at": a.finished or "",
           "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "status": "validated" if not errs else "ошибка формата", "n_items": n, "n_rejected": len(errs),
           "checked_by": "esg_agent.py check",
           "output_file": str(answer.resolve().relative_to(REPO)), "output_sha256": sha256(answer)}
    path = AGENT / "runs" / "manifest.csv"
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8-sig" if not exists else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row), delimiter=";")
        if not exists:
            w.writeheader()
        w.writerow(row)
    print(f"записано в {path}: {row['batch_id']} {row['status']}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("prepare", help="отчёт -> предложения -> партии")
    s.add_argument("source", help="PDF, TXT или JSONL страниц")
    s.add_argument("--pages", help="только эти страницы, например 5-7,12")
    s.add_argument("--report-id", help="код отчёта, например ABCD-2024-ОУР (по умолчанию имя файла)")
    s.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    s.add_argument("--esg-filter", action="store_true", help="оставить только предложения с ESG-словами (быстрее, но теряет часть заявлений)")
    s.add_argument("--out", help="папка (по умолчанию work/<код отчёта>)")
    s.set_defaults(func=cmd_prepare)
    s = sub.add_parser("make-eval", help="партии проверки на эталоне")
    s.add_argument("split", choices=("working", "heldout"))
    s.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    s.set_defaults(func=cmd_make_eval)
    s = sub.add_parser("check", help="проверка ответа модели")
    s.add_argument("batch")
    s.add_argument("answer")
    s.set_defaults(func=cmd_check)
    s = sub.add_parser("evaluate", help="сравнение с эталоном")
    s.add_argument("answers", help="папка с ответами, например llm/v1")
    s.add_argument("--prefix", default="", help="только партии с этим началом имени (working_, heldout_)")
    s.add_argument("--report", default=str(AGENT / "eval" / "результат.md"))
    s.add_argument("--errors", default=str(AGENT / "eval" / "ошибки.csv"))
    s.set_defaults(func=cmd_evaluate)
    s = sub.add_parser("export", help="таблица ESG-заявлений отчёта")
    s.add_argument("report_id")
    s.add_argument("--version", default="v1")
    s.set_defaults(func=cmd_export)
    s = sub.add_parser("manifest", help="строка журнала партии")
    s.add_argument("batch")
    s.add_argument("answer")
    s.add_argument("--model", required=True)
    s.add_argument("--thread", default="")
    s.add_argument("--prompt")
    s.add_argument("--started")
    s.add_argument("--finished")
    s.set_defaults(func=cmd_manifest)
    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
