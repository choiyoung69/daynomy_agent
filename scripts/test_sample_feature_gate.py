#!/usr/bin/env python3
"""Regression checks for observed comparison mistakes, without model/DB calls."""
from decimal import Decimal
import json
import unittest

from sample_feature_gate import encode, normalize, cases


class ComparisonTests(unittest.TestCase):
    def test_equal_instants_with_different_offsets_match(self):
        self.assertEqual(normalize("2026-08-18T10:00:00Z"),normalize("2026-08-18T19:00:00+09:00"))
        self.assertNotEqual(normalize("2026-08-18T10:00:00Z"),normalize("2026-08-18T10:00:00+09:00"))

    def test_large_decimal_survives_evidence_encoding(self):
        value={"amount":Decimal("122999999999999998.77")}
        self.assertEqual(json.loads(encode(value),parse_float=Decimal),value)

    def test_error_order_changes_but_duplicates_are_not_removed(self):
        a={"errors":[{"field":"a"},{"field":"b"}]}
        b={"errors":[{"field":"b"},{"field":"a"}]}
        self.assertEqual(normalize(a),normalize(b))
        self.assertNotEqual(normalize(a),normalize({"errors":a["errors"]+[a["errors"][0]]}))

    def test_item_order_null_and_additional_fields_remain_material(self):
        self.assertNotEqual(normalize({"items":[1,2]}),normalize({"items":[2,1]}))
        self.assertNotEqual(normalize({"value":None}),normalize({}))
        self.assertNotEqual(normalize({"value":1}),normalize({"value":1,"extra":True}))

    def test_case_names_are_unique_and_include_precision_boundary(self):
        names=[c[0] for c in cases()]
        self.assertEqual(len(names),len(set(names)))
        self.assertIn("calc-large-decimal",names)
        self.assertIn("calc-exponent",names)
        self.assertIn("news-empty-page",names)
        self.assertIn("calc-max-quantity",names)
        self.assertEqual(len(names)+1,44)


if __name__ == "__main__":
    unittest.main()
