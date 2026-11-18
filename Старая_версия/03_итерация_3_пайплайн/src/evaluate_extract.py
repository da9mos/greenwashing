"""Evaluate frozen sentence predictions without tuning or calling a model.

    python src/evaluate_extract.py --predictions llm/extract_eval/v1/all.jsonl \
        --output-dir data/extract_eval/v1

Only run after predictions and the prompt have been frozen. Bootstrap samples
whole fragments, preserving dependence between neighbouring sentences.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rel(p) -> str:
    """Путь относительно папки конвейера, чтобы в metrics.json не попадал путь с чужого компьютера."""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)
TYPES = ("обязательство", "результат", "декларация")
NEGATIVE = "не заявление"
CLASSES = TYPES + (NEGATIVE,)
SPLITS = ("рабочий", "отложенный")
PRED_FIELDS = ("sentence_id", "is_claim", "type", "esg_block", "topic", "has_number", "has_deadline")


def load_predictions(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    rows = []
    for line_number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc
        if not isinstance(row, dict) or any(k not in row for k in PRED_FIELDS):
            raise ValueError(f"Missing prediction fields at line {line_number}")
        rows.append(row)
    return rows, hashlib.sha256(raw).hexdigest()


def validate_and_join(gold: list[dict], predictions: list[dict]) -> list[tuple[dict, dict]]:
    """Reject partial runs rather than silently evaluating only answered rows."""
    if not gold:
        raise ValueError("Gold dataset is empty")
    for name, rows in (("gold", gold), ("predictions", predictions)):
        counts = Counter(r.get("sentence_id") for r in rows)
        duplicates = [key for key, count in counts.items() if count > 1]
        if duplicates:
            raise ValueError(f"Duplicate IDs in {name}: {duplicates[:5]}")
        if None in counts or "" in counts:
            raise ValueError(f"Empty sentence_id in {name}")
    gold_ids = {r["sentence_id"] for r in gold}
    pred_by_id = {r["sentence_id"]: r for r in predictions}
    missing, extra = gold_ids - pred_by_id.keys(), pred_by_id.keys() - gold_ids
    if missing or extra:
        raise ValueError(f"ID coverage mismatch: missing={len(missing)}, extra={len(extra)}; "
                         f"examples missing={sorted(missing)[:3]}, extra={sorted(extra)[:3]}")
    for r in gold:
        if r.get("final_is_claim") not in ("да", "нет"):
            raise ValueError(f"Unresolved gold claim label: {r['sentence_id']}")
        if r.get("split") not in SPLITS:
            raise ValueError(f"Unknown split: {r.get('split')!r}")
        if not r.get("fragment_id"):
            raise ValueError(f"Missing fragment_id: {r['sentence_id']}")
        if r["final_is_claim"] == "да" and r.get("final_type") not in TYPES:
            raise ValueError(f"Invalid gold type: {r['sentence_id']}")
    for p in predictions:
        if any(k not in p for k in PRED_FIELDS):
            raise ValueError(f"Missing prediction fields: {p.get('sentence_id')}")
        if p["is_claim"] not in ("да", "нет"):
            raise ValueError(f"Invalid is_claim: {p['sentence_id']}")
        if p["is_claim"] == "да":
            if p["type"] not in TYPES or p["esg_block"] not in ("E", "S", "G"):
                raise ValueError(f"Invalid prediction type/block: {p['sentence_id']}")
            if p["has_number"] not in ("да", "нет"):
                raise ValueError(f"Invalid number/deadline flag: {p['sentence_id']}")
            if p["type"] == "обязательство":
                if p["has_deadline"] not in ("да", "нет"):
                    raise ValueError(f"Invalid commitment deadline flag: {p['sentence_id']}")
            elif p["has_deadline"] not in ("", None):
                raise ValueError(f"Deadline flag only applies to commitments: {p['sentence_id']}")
            if not p["topic"]:
                raise ValueError(f"Empty topic: {p['sentence_id']}")
        elif any(p[k] not in ("", None) for k in PRED_FIELDS[2:]):
            raise ValueError(f"Non-claim must have empty semantic fields: {p['sentence_id']}")
    return [(g, pred_by_id[g["sentence_id"]]) for g in gold]


def ratio(a: int | float, b: int | float) -> float:
    return a / b if b else 0.0


def prf(tp: int, fp: int, fn: int) -> dict:
    return {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn), "tp": tp, "fp": fp, "fn": fn}


def compute_metrics(pairs: list[tuple[dict, dict]]) -> dict:
    tp = fp = fn = tn = 0
    confusion = {g: {p: 0 for p in CLASSES} for g in CLASSES}
    # Type metrics are conditional on gold=true, but missed claims remain FN.
    type_counts = {t: [0, 0, 0] for t in TYPES}
    correct_fields = Counter()
    n_claims = 0
    for gold, pred in pairs:
        g = gold["final_is_claim"] == "да"
        p = pred["is_claim"] == "да"
        tp += g and p
        fp += not g and p
        fn += g and not p
        tn += not g and not p
        gt = gold["final_type"] if g else NEGATIVE
        pt = pred["type"] if p else NEGATIVE
        confusion[gt][pt] += 1
        if g:
            n_claims += 1
            for t in TYPES:
                type_counts[t][0] += gt == t and pt == t
                type_counts[t][1] += gt != t and pt == t
                type_counts[t][2] += gt == t and pt != t
            for field in ("esg_block", "topic", "has_number", "has_deadline"):
                correct_fields[field] += p and gold.get("final_" + field) == pred.get(field)
    type_scores = {t: {**prf(*counts), "support": sum(confusion[t].values())}
                   for t, counts in type_counts.items()}
    all_class_scores = {}
    for t in CLASSES:
        class_tp = confusion[t][t]
        class_fp = sum(confusion[other][t] for other in CLASSES if other != t)
        class_fn = sum(confusion[t][other] for other in CLASSES if other != t)
        all_class_scores[t] = prf(class_tp, class_fp, class_fn)
    return {
        "n_sentences": len(pairs), "n_fragments": len({g["fragment_id"] for g, _ in pairs}),
        "n_gold_claims": n_claims, "binary": {**prf(tp, fp, fn), "tn": tn},
        "type_macro_f1": sum(v["f1"] for v in type_scores.values()) / len(TYPES),
        "type_per_class": type_scores,
        "four_class_macro_f1": sum(v["f1"] for v in all_class_scores.values()) / len(CLASSES),
        "type_macro_f1_end_to_end": sum(all_class_scores[t]["f1"] for t in TYPES) / len(TYPES),
        "field_accuracy_on_gold_claims": {k: ratio(correct_fields[k], n_claims)
            for k in ("esg_block", "topic", "has_number", "has_deadline")},
        "confusion_gold_rows_predicted_columns": confusion,
    }


def resample_fragments(pairs: list[tuple[dict, dict]], rng: random.Random) -> list[tuple[dict, dict]]:
    groups: dict[str, list] = defaultdict(list)
    for pair in pairs:
        groups[pair[0]["fragment_id"]].append(pair)
    ids = sorted(groups)
    return [pair for key in rng.choices(ids, k=len(ids)) for pair in groups[key]] if ids else []


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def bootstrap_ci(pairs: list[tuple[dict, dict]], repetitions: int = 1000, seed: int = 20261115) -> dict:
    if repetitions < 1:
        raise ValueError("Bootstrap repetitions must be positive")
    if not pairs:
        return {"method": "fragment bootstrap percentile", "repetitions": repetitions, "seed": seed,
                "n_fragments": 0, "intervals": {}}
    rng = random.Random(seed)
    values: dict[str, list[float]] = defaultdict(list)
    for _ in range(repetitions):
        m = compute_metrics(resample_fragments(pairs, rng))
        for key in ("precision", "recall", "f1"):
            values["binary_" + key].append(m["binary"][key])
        values["type_macro_f1"].append(m["type_macro_f1"])
        values["type_macro_f1_end_to_end"].append(m["type_macro_f1_end_to_end"])
        values["esg_block_accuracy"].append(m["field_accuracy_on_gold_claims"]["esg_block"])
    return {"method": "fragment bootstrap percentile", "confidence": 0.95,
            "repetitions": repetitions, "seed": seed,
            "n_fragments": len({g["fragment_id"] for g, _ in pairs}),
            "intervals": {k: [percentile(v, 0.025), percentile(v, 0.975)] for k, v in values.items()}}


def evaluate(gold: list[dict], predictions: list[dict], repetitions: int, seed: int) -> tuple[dict, list[dict]]:
    pairs = validate_and_join(gold, predictions)
    groups: dict[str, list] = {"all": pairs}
    for split in SPLITS:
        subset = [pair for pair in pairs if pair[0]["split"] == split]
        groups[f"split/{split}"] = subset
        for part in sorted({g["sample_part"] for g, _ in subset}):
            groups[f"split/{split}/sample_part/{part}"] = [p for p in subset if p[0]["sample_part"] == part]
    for part in sorted({g["sample_part"] for g, _ in pairs}):
        groups[f"sample_part/{part}"] = [p for p in pairs if p[0]["sample_part"] == part]
    result = {key: {**compute_metrics(subset), "bootstrap": bootstrap_ci(subset, repetitions, seed)}
              for key, subset in groups.items()}
    errors = []
    for gold_row, pred in pairs:
        fields = ["is_claim"]
        if gold_row["final_is_claim"] == "да":
            fields += ["type", "esg_block", "topic", "has_number", "has_deadline"]
        wrong = [f for f in fields if gold_row["final_" + f] != pred.get(f)]
        if wrong:
            row = {k: gold_row.get(k, "") for k in ("sentence_id", "fragment_id", "report_id", "page",
                   "split", "sample_part", "sentence")}
            row["mismatched_fields"] = ",".join(wrong)
            for field in PRED_FIELDS[1:]:
                row["gold_" + field] = gold_row.get("final_" + field, "")
                row["pred_" + field] = pred.get(field, "")
            errors.append(row)
    return result, errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from text_versions import gold_csv
    # по умолчанию — эталон на действующей версии текстов; метки во всех версиях одинаковые
    parser.add_argument("--gold", type=Path, default=gold_csv())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261115)
    args = parser.parse_args()
    try:
        predictions, prediction_hash = load_predictions(args.predictions)
        gold_raw = args.gold.read_bytes()
        gold = list(csv.DictReader(io.StringIO(gold_raw.decode("utf-8-sig")), delimiter=";"))
        metrics, errors = evaluate(gold, predictions, args.bootstrap, args.seed)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_json, output_errors = args.output_dir / "metrics.json", args.output_dir / "errors.csv"
        if output_json.exists() or output_errors.exists():
            raise ValueError("Output exists; use a new version directory to preserve frozen results")
        document = {
            "prediction_sha256": prediction_hash, "gold_sha256": hashlib.sha256(gold_raw).hexdigest(),
            "prediction_path": _rel(args.predictions), "gold_path": _rel(args.gold),
            "definitions": {
                "zero_division": 0,
                "type_macro_f1": "Three types, only gold claims; missed claims are FN. All three classes always included.",
                "field_accuracy": "All gold claims, including missed claims as incorrect.",
                "four_class_macro_f1": "All sentences, all four classes including non-claim.",
                "type_macro_f1_end_to_end": "Three type F1s on all sentences; false-positive extracted claims count as FP.",
                "bootstrap": "Resample whole fragment_id clusters with replacement within each reported subset.",
                "scope": "Sentence classification quality only; does not measure production candidate-selection recall.",
            }, "groups": metrics,
        }
        output_json.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        columns = ["sentence_id", "fragment_id", "report_id", "page", "split", "sample_part", "sentence",
                   "mismatched_fields"] + [prefix + f for f in PRED_FIELDS[1:] for prefix in ("gold_", "pred_")]
        with output_errors.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";")
            writer.writeheader()
            writer.writerows(errors)
        print(json.dumps({"prediction_sha256": prediction_hash, "groups": len(metrics),
                          "error_rows": len(errors), "output_dir": str(args.output_dir)}, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Evaluation failed: {exc}\n")


if __name__ == "__main__":
    main()
