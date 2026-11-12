"""Нарезка текста страниц на куски ~1 500 знаков с номером страницы. Без модели.

    python src/chunk.py            # все data/pages/*.jsonl -> data/chunks/<report_id>.jsonl

Кусок никогда не переходит через границу страницы (чтобы номер страницы у цитаты был точным).
Режем по абзацам, длинный абзац — по предложениям. Куски короче 200 знаков (колонтитулы,
номера) приклеиваются к соседнему куску той же страницы или отбрасываются, если страница пустая.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX = 1500
MIN = 200
SENT = re.compile(r"(?<=[.!?…])\s+(?=[«\"(A-ZА-ЯЁ0-9])")


def pieces(text: str) -> list[str]:
    out = []
    for para in re.split(r"\n\s*\n", text):
        para = re.sub(r"\s*\n\s*", " ", para).strip()
        if not para:
            continue
        if len(para) <= MAX:
            out.append(para)
        else:
            out.extend(s.strip() for s in SENT.split(para) if s.strip())
    return out


def chunk_page(text: str) -> list[str]:
    chunks, cur = [], ""
    for p in pieces(text):
        while len(p) > MAX:  # одно сверхдлинное «предложение» (таблица) режем по пробелу
            cut = p.rfind(" ", 0, MAX)
            cut = cut if cut > MAX // 2 else MAX
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(p[:cut].strip())
            p = p[cut:].strip()
        if len(cur) + len(p) + 1 <= MAX:
            cur = f"{cur} {p}".strip()
        else:
            chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < MIN and len(merged[-1]) + len(c) + 1 <= MAX + MIN:
            merged[-1] += " " + c
        else:
            merged.append(c)
    return [c for c in merged if len(c) >= MIN or len(merged) == 1 and len(c) >= 80]


def is_garbage(text: str) -> bool:
    """Кусок из сломанного текстового слоя PDF (шрифт без таблицы символов): много управляющих и «�»."""
    bad = sum(1 for ch in text if ch == "\ufffd" or (ord(ch) < 32 and ch not in "\n\t\r"))
    letters = sum(ch.isalpha() for ch in text)
    return bad / max(len(text), 1) > 0.02 or letters / max(len(text), 1) < 0.4


def main() -> None:
    src, dst = ROOT / "data" / "pages", ROOT / "data" / "chunks"
    dst.mkdir(parents=True, exist_ok=True)
    total = dropped = 0
    for f in sorted(src.glob("*.jsonl")):
        n = 0
        with open(f, encoding="utf-8") as fin, open(dst / f.name, "w", encoding="utf-8") as fout:
            for line in fin:
                pg = json.loads(line)
                for c in chunk_page(pg.get("text", "")):
                    if is_garbage(c):
                        dropped += 1
                        continue
                    n += 1
                    fout.write(json.dumps({"chunk_id": f"{pg['report_id']}_c{n:04d}", "report_id": pg["report_id"],
                                           "page": pg["page"], "text": c}, ensure_ascii=False) + "\n")
        total += n
        print(f"{f.stem}: {n} кусков")
    print("Всего кусков:", total, "| выброшено мусорных (сломанный текст или почти без букв):", dropped)


if __name__ == "__main__":
    main()
