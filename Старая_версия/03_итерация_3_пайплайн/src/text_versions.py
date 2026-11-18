"""Какие тексты отчётов и таблицы брать. Одно место для всех скриптов.

CURRENT — действующая версия текстов. Новые этапы (новые партии, проверка эталона, оценка)
по умолчанию берут её. Замороженные результаты (извлечение Георгия extract v1) собраны на v2
и проверяются хэшами — для них скрипты сами берут v2, так что их пересборка не ломается.

Версии:
  v2  data/pages, data/chunks              — разбор PyMuPDF 12.11.2026 (claims.csv, gold_extract.csv)
  v3  data/pages_v3, data/chunks_v3        — чистка 16.11.2026 (УСТАРЕЛО: дефисы по словарю, «№»→9 в ММК 2025)
  v4  data/pages_v4, data/chunks_v4        — 16.11.2026 вечер: дефисы и шрифт по самим PDF (действует)
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = "v4"
FROZEN_EXTRACT_V1 = "v2"   # на этих текстах собрано и заморожено извлечение extract v1

_PAGES = {"v2": "data/pages", "v3": "data/pages_v3", "v4": "data/pages_v4"}
_CHUNKS = {"v2": "data/chunks", "v3": "data/chunks_v3", "v4": "data/chunks_v4"}
_CLAIMS = {"v2": "data/out/claims.csv", "v3": "data/out/claims_text_v3.csv", "v4": "data/out/claims_text_v4.csv"}
_GOLD = {"v2": "data/out/gold_extract.csv", "v3": "data/out/gold_extract_text_v3.csv",
         "v4": "data/out/gold_extract_text_v4.csv"}
VERSIONS = tuple(_PAGES)


def _get(table: dict, version: str | None) -> Path:
    v = version or CURRENT
    if v not in table:
        raise ValueError(f"нет версии текстов {v!r}; есть: {', '.join(table)}")
    return ROOT / table[v]


def pages_dir(version: str | None = None) -> Path:
    return _get(_PAGES, version)


def chunks_dir(version: str | None = None) -> Path:
    return _get(_CHUNKS, version)


def claims_csv(version: str | None = None) -> Path:
    return _get(_CLAIMS, version)


def gold_csv(version: str | None = None) -> Path:
    return _get(_GOLD, version)

