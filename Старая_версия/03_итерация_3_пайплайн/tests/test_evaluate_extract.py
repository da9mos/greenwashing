"""Synthetic tests only: these do not open or reveal the held-out gold labels."""
import importlib.util
from pathlib import Path
import random
import unittest

PATH = Path(__file__).resolve().parents[1] / "src/evaluate_extract.py"
SPEC = importlib.util.spec_from_file_location("evaluate_extract", PATH)
ev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)


def gold(sid, claim=True, typ="результат", fragment="f1"):
    return {"sentence_id": sid, "fragment_id": fragment, "split": "отложенный", "sample_part": "случайный",
            "final_is_claim": "да" if claim else "нет", "final_type": typ if claim else "",
            "final_esg_block": "E" if claim else "", "final_topic": "вода" if claim else "",
            "final_has_number": "нет" if claim else "", "final_has_deadline": "нет" if claim and typ == "обязательство" else ""}


def pred(sid, claim=True, typ="результат"):
    return {"sentence_id": sid, "is_claim": "да" if claim else "нет", "type": typ if claim else "",
            "esg_block": "E" if claim else "", "topic": "вода" if claim else "",
            "has_number": "нет" if claim else "", "has_deadline": "нет" if claim and typ == "обязательство" else ""}


class EvaluationTests(unittest.TestCase):
    def test_missed_claim_stays_in_recall_and_type_denominator(self):
        pairs = ev.validate_and_join([gold("a"), gold("b")], [pred("a"), pred("b", False)])
        m = ev.compute_metrics(pairs)
        self.assertEqual(m["binary"]["recall"], 0.5)
        self.assertEqual(m["type_per_class"]["результат"]["fn"], 1)
        self.assertAlmostEqual(m["type_per_class"]["результат"]["f1"], 2 / 3)
        self.assertEqual(m["field_accuracy_on_gold_claims"]["esg_block"], 0.5)
        self.assertEqual(m["confusion_gold_rows_predicted_columns"]["результат"]["не заявление"], 1)

    def test_duplicate_missing_and_extra_ids_fail(self):
        cases = [([pred("a"), pred("a")], "Duplicate"),
                 ([], "missing=1"), ([pred("a"), pred("z")], "extra=1")]
        for predictions, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                ev.validate_and_join([gold("a")], predictions)

    def test_all_negative_is_defined(self):
        pairs = ev.validate_and_join([gold("a", False)], [pred("a", False)])
        m = ev.compute_metrics(pairs)
        self.assertEqual(m["binary"]["tn"], 1)
        self.assertEqual(m["binary"]["f1"], 0)
        self.assertEqual(m["type_macro_f1"], 0)
        ci = ev.bootstrap_ci(pairs, repetitions=5)
        self.assertEqual(ci["intervals"]["binary_f1"], [0, 0])

    def test_cluster_resampling_keeps_whole_fragments(self):
        pairs = [(gold("a", fragment="f1"), pred("a")),
                 (gold("b", fragment="f1"), pred("b")),
                 (gold("c", fragment="f2"), pred("c"))]
        for seed in range(30):
            sampled = ev.resample_fragments(pairs, random.Random(seed))
            counts = ev.Counter(g["sentence_id"] for g, _ in sampled)
            self.assertEqual(counts["a"], counts["b"])
            self.assertEqual(counts["a"] + counts["c"], 2)
        self.assertEqual(ev.bootstrap_ci(pairs, 10, 7), ev.bootstrap_ci(pairs, 10, 7))

    def test_wrong_type_and_false_positive_separate_scopes(self):
        pairs = ev.validate_and_join([gold("a"), gold("b", False)],
                                     [pred("a", typ="обязательство"), pred("b")])
        m = ev.compute_metrics(pairs)
        self.assertEqual(m["binary"]["precision"], 0.5)
        self.assertEqual(m["type_per_class"]["обязательство"]["fp"], 1)
        self.assertEqual(m["type_per_class"]["результат"]["fp"], 0)
        self.assertEqual(m["confusion_gold_rows_predicted_columns"]["не заявление"]["результат"], 1)


if __name__ == "__main__":
    unittest.main()
