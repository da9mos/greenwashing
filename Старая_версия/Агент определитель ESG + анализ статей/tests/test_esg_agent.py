"""Тесты механики агента-определителя ESG (без модели).

Запуск из корня репозитория:  python -m pytest "Агент определитель ESG + анализ статей/tests" -q
"""
import json
import re
import sys
from pathlib import Path

import pytest

AGENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT / "scripts"))
import esg_agent as ea  # noqa: E402


# --- деление на предложения -------------------------------------------------
def test_split_keeps_abbreviations():
    s = ea.split_sentences("Закуплено и выработано 36,5 тыс. МВт·ч зелёной энергии. Подробнее см. Приложение 4.")
    assert s == ["Закуплено и выработано 36,5 тыс. МВт·ч зелёной энергии.", "Подробнее см. Приложение 4."]


def test_split_page_reference_joined_only_before_digit():
    s = ea.split_sentences("Подробнее на с. 45 отчёта. С. Иванов назначен директором.")
    assert s[0] == "Подробнее на с. 45 отчёта."


def test_split_removes_hyphenation_and_soft_hyphen():
    s = ea.split_sentences("Компания сокра-\nтила вы­бросы на 5%.")
    assert s == ["Компания сократила выбросы на 5%."]


def test_noise_filter():
    assert ea.is_noise("01.")
    assert ea.is_noise("165,3 163,3 174,8 2021 2022 2023 1,1 0,9")
    assert not ea.is_noise("Компания сократила выбросы парниковых газов на 5%.")


def test_parse_pages():
    assert ea.parse_pages("5-7,12") == {5, 6, 7, 12}


# --- справочники ------------------------------------------------------------
def test_taxonomy_has_all_blocks_and_other():
    t = ea.taxonomy()
    assert set(t) == {"E", "S", "G"}
    for b in t:
        assert "другое" in t[b]
    assert sum(len(v) for v in t.values()) == 21


def test_prompt_topics_match_taxonomy():
    """Таблица тем в действующем промпте совпадает с taxonomy.csv."""
    text = ea.PROMPT.read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([ESG]) \| ([^|]+?) \|", text, flags=re.M)
    in_prompt = {(b, t.strip()) for b, t in rows}
    in_csv = {(b, t) for b, ts in ea.taxonomy().items() for t in ts}
    assert in_prompt == in_csv


def test_prompt_rules_are_known_to_checker():
    """Каждый номер правила в таблицах промпта проходит проверку RULE_RE, и наоборот нет лишних."""
    text = ea.PROMPT.read_text(encoding="utf-8")
    nums = set(re.findall(r"^\| ([НЗБТ]\d+) \|", text, flags=re.M))
    assert nums, "в промпте не найдены правила"
    for n in nums:
        assert ea.RULE_RE.match(n), n
    assert not ea.RULE_RE.match("Т25") and not ea.RULE_RE.match("Н9")


# --- проверка ответа --------------------------------------------------------
BATCH = [{"sentence_id": "X_s1", "sentence": "a"}, {"sentence_id": "X_s2", "sentence": "b"}]


def good():
    return [
        {"sentence_id": "X_s1", "is_esg": "да", "block": "E", "topic": "климат", "block2": "G",
         "confidence": "высокая", "rule": "Б3", "essence": "цели по выбросам", "reason": "предмет — климат"},
        {"sentence_id": "X_s2", "is_esg": "нет", "block": "", "topic": "", "block2": "",
         "confidence": "высокая", "rule": "Н4", "essence": "", "reason": "заголовок"},
    ]


def test_validate_ok():
    assert ea.validate(BATCH, good()) == []


@pytest.mark.parametrize("field,value,needle", [
    ("topic", "вода", "не из списка"),        # тема E при букве S
    ("block2", "S", "block2"),                 # вторая буква равна первой
    ("rule", "Т99", "нет такого правила"),
    ("confidence", "", "confidence"),
    ("essence", "", "пустая essence"),
])
def test_validate_catches(field, value, needle):
    ans = good()
    ans[0]["block"] = "S" if field in ("topic", "block2") else ans[0]["block"]
    if field == "topic":
        ans[0]["topic"] = value
    elif field == "block2":
        ans[0]["topic"], ans[0]["block2"] = "обучение", value
    else:
        ans[0][field] = value
    assert any(needle in e for e in ea.validate(BATCH, ans))


def test_validate_missing_and_duplicates():
    ans = good()
    ans[1] = dict(ans[0])
    errs = ea.validate(BATCH, ans)
    assert any("нет ответа" in e for e in errs) and any("повторы" in e for e in errs)


def test_validate_no_fields_filled_for_non_claim():
    ans = good()
    ans[1]["block"] = "E"
    assert any("заполнено" in e for e in ea.validate(BATCH, ans))


# --- метрика -----------------------------------------------------------------
def test_kappa_perfect_and_chance():
    assert ea.kappa([("да", "да"), ("нет", "нет")]) == pytest.approx(1.0)
    assert ea.kappa([("да", "да"), ("да", "нет"), ("нет", "да"), ("нет", "нет")]) == pytest.approx(0.0)


# --- сохранённые ответы агента проходят проверку ------------------------------
def test_saved_answers_are_valid():
    n = 0
    for ans_path in sorted((AGENT / "llm").glob("*/*.json")):
        folder = ans_path.parent.name
        if folder.startswith("eval_"):
            batch_path = AGENT / "eval" / "batches" / (ans_path.stem + ".jsonl")
        else:
            rid = ans_path.stem.rsplit("_b", 1)[0]
            batch_path = AGENT / "work" / rid / "batches" / (ans_path.stem + ".jsonl")
        if not batch_path.exists():
            continue
        batch = [json.loads(l) for l in batch_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert ea.validate(batch, ea.load_answer(ans_path)) == [], ans_path.name
        n += 1
    assert n >= 22
