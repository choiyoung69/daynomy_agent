#!/usr/bin/env python3
"""Checker self-tests: meaningful false-positive and environment-boundary probes.

These do not claim that a real Rust server or PostgreSQL query has passed.
"""
from decimal import Decimal
import json
import unittest
from unittest.mock import Mock, patch

from acceptance import EnvironmentFailure
from service_acceptance import TestDatabase, cases, equal, execute_case


class EqualitySafetyTests(unittest.TestCase):
    def test_rejects_missing_and_extra_contract_fields(self):
        for value in ({}, {"risk":"ok","watchPoint":"ok","extra":True}):
            with self.assertRaises(AssertionError):
                equal(value,{"risk":"ok","watchPoint":"ok"})

    def test_rejects_numeric_strings_booleans_and_precision_loss(self):
        for value in ("10.1234", True, Decimal("10.1235"), 10.1234):
            with self.assertRaises(AssertionError):
                equal(value,Decimal("10.1234"))

    def test_equivalent_decimal_scale_and_instant_are_allowed(self):
        equal(Decimal("10.123400"),Decimal("10.1234"))
        equal("2020-01-02T12:04:05+09:00","2020-01-02T03:04:05Z")

    def test_rejects_order_changes(self):
        with self.assertRaises(AssertionError): equal([2,1],[1,2])

    def test_report_failure_messages_do_not_include_response_values(self):
        secret="must-not-be-logged-value"
        with self.assertRaises(AssertionError) as caught:
            equal({"token":secret},{"token":"expected"})
        self.assertNotIn(secret,str(caught.exception))


class ExecutionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.case={"name":"probe","path":"/api/news","expected":{"items":[]},
                   "status":200,"data":None,"check":None,"csrf":True}
        self.client=Mock()
        self.client.send.return_value=(200,{"Content-Type":"application/json"},b'{"items":[]}')
        self.db=Mock()
        self.db.snapshot.side_effect=["unchanged","unchanged"]

    def test_good_transport_passes(self):
        execute_case(self.case,self.client,self.db,None)

    def test_unimplemented_endpoint_is_failure(self):
        self.client.send.return_value=(501,{"Content-Type":"application/json"},b'{"items":[]}')
        with self.assertRaisesRegex(AssertionError,"HTTP status"):
            execute_case(self.case,self.client,self.db,None)

    def test_success_response_with_db_mutation_is_failure(self):
        self.db.snapshot.side_effect=["before","after"]
        with self.assertRaisesRegex(AssertionError,"persistent DB"):
            execute_case(self.case,self.client,self.db,None)

    def test_db_mutation_is_checked_even_on_wrong_http_status(self):
        self.db.snapshot.side_effect=["before","after"]
        self.client.send.return_value=(500,{},b'')
        with self.assertRaisesRegex(AssertionError,"persistent DB"):
            execute_case(self.case,self.client,self.db,None)
        self.assertEqual(self.db.snapshot.call_count,2)

    def test_missing_csrf_setup_cannot_pass_post(self):
        self.case["data"]={"holdings":[]}
        with self.assertRaisesRegex(AssertionError,"CSRF setup"):
            execute_case(self.case,self.client,self.db,None)
        self.client.send.assert_not_called()

    def test_invalid_json_is_failure(self):
        self.client.send.return_value=(200,{"Content-Type":"application/json"},b'not json')
        with self.assertRaisesRegex(AssertionError,"Invalid response JSON"):
            execute_case(self.case,self.client,self.db,None)

    def test_nonlocal_and_wrong_db_rejected_before_connection(self):
        for url in ("postgresql://127.0.0.1/production", "postgresql://127.0.0.1/feedback_test",
                    "postgresql://remote.example/daynomy_service_test"):
            with patch("service_acceptance.Database.__init__") as connect:
                with self.assertRaises((AssertionError,EnvironmentFailure)): TestDatabase(url)
                connect.assert_not_called()

    def test_case_names_unique_and_tests_include_hidden_precision_and_mutation_guards(self):
        all_cases=cases("2026-10-21T03:00:00Z","2020-01-02T03:04:05Z")
        names=[c["name"] for c in all_cases]
        self.assertEqual(len(names),len(set(names)))
        self.assertGreaterEqual(len(names),70)
        for name in ("price-910003","calculate-csrf-required","keywords-hidden",
                     "content-search-cross-source-dedup","calculate-partial-nulls"):
            self.assertIn(name,names)
        # A zero-price mutant cannot pass the independently fixed precision case.
        price=next(c for c in all_cases if c["name"]=="price-910003")
        mutant=dict(price["expected"],closePrice=0)
        with self.assertRaises(AssertionError): equal(mutant,price["expected"])


if __name__=="__main__": unittest.main()
