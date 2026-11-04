#!/usr/bin/env python3
"""Check context selection and readiness decisions with isolated synthetic fixtures."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="knowledge-context-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / "knowledge", self.root / "knowledge")
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/knowledge.py", self.root / "scripts/knowledge.py")
        shutil.copy2(ROOT / "scripts/knowledge_sources.py", self.root / "scripts/knowledge_sources.py")
        registry = json.loads((self.root / "knowledge/sources.json").read_text())
        for source in registry["sources"]:
            if source["kind"] == "local":
                target = self.root / source["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / source["path"], target)
        # WebView pilot metadata links its explicit scope contract.
        shutil.copytree(ROOT / "spec/webview", self.root / "spec/webview")
        # Wiki history links grow across runs; preserve their real read-only targets.
        (self.root / "runs").mkdir(exist_ok=True)
        for path in (ROOT / "runs").glob("*.md"):
            shutil.copy2(path, self.root / "runs" / path.name)
        (self.root / "clients/android").mkdir(parents=True)
        shutil.copy2(ROOT / "clients/android/README.md", self.root / "clients/android/README.md")

    def run_context(self, platform="ios", guarded=False, check_only=False):
        args = [sys.executable, str(self.root / "scripts/knowledge.py"), "context",
                "--feature", "stock-search-price", "--platform", platform]
        if guarded:
            args.append("--require-ready")
        if check_only:
            args.append("--check-only")
        return subprocess.run(args, capture_output=True, text=True, cwd=self.root)

    def test_check_only_preserves_ready_and_blocked_decisions_without_bodies(self):
        for prepared in (False, True):
            if prepared:
                self.prepare_synthetic_ios()
            result=self.run_context(guarded=True,check_only=True)
            self.assertEqual(result.returncode,0 if prepared else 2,result.stdout+result.stderr)
            self.assertNotIn('--- knowledge/',result.stdout)
            self.assertNotIn('Selected source records:',result.stdout)

    def edit_json(self, relative, mutate):
        path = self.root / relative
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def prepare_synthetic_ios(self):
        def prepare(packs):
            platform = packs["platforms"]["ios"]
            platform["selected_versions"] = {key: "synthetic-test-value" for key in platform["required_version_fields"]}
            platform["pending_decisions"] = []
            platform["topics"] = {key: "documented" for key in platform["topics"]}
        self.edit_json("knowledge/packs.json", prepare)
        for relative in ("wiki/platforms/ios.md", "wiki/shared/client-porting-baseline.md"):
            path = self.root / "knowledge" / relative
            path.write_text(path.read_text().replace("review_status: draft", "review_status: static-reviewed"))

    def test_each_platform_selects_common_and_own_documents_only(self):
        for slug in ("android", "ios", "react-native", "flutter", "webview"):
            with self.subTest(platform=slug):
                result = self.run_context(slug)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                headings = [line for line in result.stdout.splitlines() if line.startswith("--- knowledge/")]
                self.assertEqual(headings, [
                    "--- knowledge/wiki/projects/daynomy/stock-search-price.md ---",
                    "--- knowledge/wiki/shared/client-porting-baseline.md ---",
                    "--- knowledge/wiki/shared/error-retry-cancel.md ---",
                    "--- knowledge/wiki/shared/data-semantics.md ---",
                    "--- knowledge/wiki/shared/build-validation.md ---",
                    "--- knowledge/wiki/shared/ui-state-navigation.md ---",
                    "--- knowledge/wiki/shared/testing-migration.md ---",
                    *[f"--- knowledge/wiki/languages/{language}.md ---" for language in {
                        "android": ["kotlin"], "ios": ["swift"], "react-native": ["typescript"],
                        "flutter": ["dart"], "webview": ["typescript", "kotlin", "swift"]}[slug]],
                    f"--- knowledge/wiki/platforms/{slug}.md ---",
                    f"--- knowledge/wiki/packages/{ {'android': 'android-kotlin', 'ios': 'ios-swift', 'react-native': 'react-native-typescript', 'flutter': 'flutter-dart', 'webview': 'webview'}[slug] }/index.md ---",
                    *[f"--- knowledge/wiki/packages/{ {'android': 'android-kotlin', 'ios': 'ios-swift', 'react-native': 'react-native-typescript', 'flutter': 'flutter-dart', 'webview': 'webview'}[slug] }/{topic}.md ---" for topic in [
                        "types-and-json", "numbers-and-money", "dates-and-unicode", "collections-and-models",
                        "async-and-cancellation", "state-and-navigation", "errors-and-transactions", "modules-and-testing",
                        *(["auth-and-storage"] if slug == "webview" else [])]],
                ])
                self.assertNotIn("expected_points", result.stdout)
                guarded = self.run_context(slug, guarded=True)
                self.assertEqual(guarded.returncode, 0 if slug in ("android", "webview") else 2, guarded.stdout + guarded.stderr)
                if slug not in ("android", "webview"):
                    self.assertNotIn("--- knowledge/", guarded.stdout)
                else:
                    self.assertIn("READY FOR IMPLEMENTATION", guarded.stdout)

    def test_synthetic_ready_state_can_emit_then_missing_version_blocks(self):
        self.prepare_synthetic_ios()
        result = self.run_context(guarded=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("READY FOR IMPLEMENTATION", result.stdout)
        self.edit_json("knowledge/packs.json", lambda value: value["platforms"]["ios"]["selected_versions"].pop("ios-min"))
        result = self.run_context(guarded=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("target version is not selected: ios-min", result.stdout)

    def test_changed_source_prevents_context_delivery(self):
        path = self.root / "reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts"
        path.write_bytes(path.read_bytes() + b"\n")
        result = self.run_context()
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed source", result.stdout)
        self.assertNotIn("--- knowledge/", result.stdout)

    def test_missing_required_topic_is_invalid(self):
        self.edit_json("knowledge/packs.json", lambda value: value["platforms"]["ios"]["topics"].pop("language-data"))
        result = self.run_context()
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required topic language-data", result.stderr)

    def test_modified_external_snapshot_prevents_context_delivery(self):
        # A synthetic pin makes this test independent of live network and current capture coverage.
        import hashlib
        relative = "knowledge/raw/external/E01/synthetic.txt"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        original = b"synthetic original"
        path.write_bytes(original)
        def add_snapshot(value):
            source = next(item for item in value["sources"] if item["id"] == "E01")
            source["content_snapshot"] = {"path": relative, "bytes": len(original),
                                          "sha256": hashlib.sha256(original).hexdigest()}
        self.edit_json("knowledge/sources.json", add_snapshot)
        path.write_bytes(b"changed bytes")
        result = self.run_context()
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid external snapshot", result.stdout)
        self.assertNotIn("--- knowledge/", result.stdout)

    def test_unreviewed_source_blocks_synthetic_ready_state(self):
        self.prepare_synthetic_ios()
        def unreview(value):
            next(source for source in value["sources"] if source["id"] == "E13")["review_status"] = "catalogued"
        self.edit_json("knowledge/sources.json", unreview)
        result = self.run_context(guarded=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("source not yet reviewed: E13", result.stdout)

    def test_missing_language_mapping_is_invalid(self):
        self.edit_json("knowledge/packs.json", lambda value: value["platforms"]["webview"].update(language_packages=["typescript"]))
        result = self.run_context("webview")
        self.assertEqual(result.returncode, 1)
        self.assertIn("webview: detailed package languages mismatch", result.stderr)

    def test_language_package_emits_only_requested_language(self):
        result = subprocess.run([sys.executable, str(self.root / "scripts/knowledge.py"),
                                 "package", "--language", "kotlin"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--- knowledge/wiki/languages/kotlin.md ---", result.stdout)
        self.assertNotIn("--- knowledge/wiki/languages/swift.md ---", result.stdout)
        self.assertNotIn("--- knowledge/wiki/platforms/", result.stdout)

    def test_transaction_feature_selects_auth_and_transaction_knowledge(self):
        result = subprocess.run([sys.executable, str(self.root / "scripts/knowledge.py"), "context",
                                 "--feature", "portfolio-ledger", "--platform", "flutter"],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--- knowledge/wiki/shared/auth-storage.md ---", result.stdout)
        self.assertIn("--- knowledge/wiki/shared/transactions-concurrency.md ---", result.stdout)
        self.assertIn("--- knowledge/wiki/languages/dart.md ---", result.stdout)
        self.assertNotIn("--- knowledge/wiki/languages/kotlin.md ---", result.stdout)

    def test_deferred_feature_cannot_emit_ready_context(self):
        self.prepare_synthetic_ios()
        result = subprocess.run([sys.executable, str(self.root / "scripts/knowledge.py"), "context",
                                 "--feature", "notifications-deferred", "--platform", "ios", "--require-ready"],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("feature is deferred", result.stdout)
        self.assertNotIn("--- knowledge/", result.stdout)

    def test_missing_service_context_fails_coverage(self):
        def remove_account_context(value):
            value["features"].pop("account")
            # Keep platform metadata valid so coverage reaches the missing
            # service mapping, independently of the live approved feature scope.
            for platform in value["platforms"].values():
                if "approved_features" in platform:
                    platform["approved_features"] = ["stock-search-price"]
        self.edit_json("knowledge/packs.json", remove_account_context)
        result = subprocess.run([sys.executable, str(self.root / "scripts/knowledge.py"), "coverage"],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("feature has no context mapping: account", result.stderr)

    def run_package(self, *extra):
        return subprocess.run([sys.executable, str(self.root / "scripts/knowledge.py"), "package", *extra],
                              cwd=self.root, capture_output=True, text=True)

    def test_topic_filter_emits_one_detailed_package_and_deduplicates(self):
        result = self.run_package("--package", "android-kotlin", "--topic", "async-and-cancellation",
                                  "--topic", "async-and-cancellation")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        headings = [line for line in result.stdout.splitlines() if line.startswith("--- knowledge/")]
        self.assertEqual(headings, ["--- knowledge/wiki/packages/android-kotlin/index.md ---",
                                   "--- knowledge/wiki/packages/android-kotlin/async-and-cancellation.md ---"])

    def test_unknown_topic_and_path_escape_rejected(self):
        for topic in ("unknown", "../../ios-swift/types-and-json"):
            result = self.run_package("--package", "android-kotlin", "--topic", topic)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown detailed topic", result.stderr)
            self.assertNotIn("--- knowledge/", result.stdout)

    def test_missing_detailed_topic_is_invalid(self):
        self.edit_json("knowledge/packs.json", lambda value: value["packages"]["ios-swift"]["topics"].pop("types-and-json"))
        result = self.run_context()
        self.assertEqual(result.returncode, 1)
        self.assertIn("nine detailed topics are required", result.stderr)

    def test_detail_mapping_cannot_substitute_another_platform(self):
        self.edit_json("knowledge/packs.json", lambda value: value["platforms"]["ios"].update(implementation_package="android-kotlin"))
        result = self.run_context()
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing or unexpected detailed package", result.stderr)

    def test_topic_context_retains_feature_contract_and_limits_platform(self):
        result = subprocess.run([sys.executable, str(self.root / "scripts/knowledge.py"), "context",
                                 "--feature", "portfolio-ledger", "--platform", "flutter",
                                 "--topic", "errors-and-transactions"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--- knowledge/wiki/shared/transactions-concurrency.md ---", result.stdout)
        self.assertIn("--- knowledge/wiki/packages/flutter-dart/errors-and-transactions.md ---", result.stdout)
        self.assertNotIn("--- knowledge/wiki/packages/flutter-dart/types-and-json.md ---", result.stdout)
        self.assertNotIn("--- knowledge/wiki/packages/ios-swift/", result.stdout)

    def test_code_invocation_is_not_a_link_but_real_broken_link_fails(self):
        path = self.root / "knowledge/wiki/packages/webview/types-and-json.md"
        path.write_text(path.read_text() + "\n```typescript\nnative[message.method](message.payload)\n```\n")
        result = self.run_context()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path.write_text(path.read_text() + "\n[broken](missing.md)\n")
        result = self.run_context()
        self.assertEqual(result.returncode, 1)
        self.assertIn("broken local link missing.md", result.stdout)

    def test_refreshed_source_hash_cannot_hide_stale_execution_evidence(self):
        import hashlib
        relative = "knowledge/examples/dart/core.dart"
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n// synthetic changed source\n")
        def update_hash(registry):
            next(source for source in registry["sources"] if source.get("path") == relative)["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.edit_json("knowledge/sources.json", update_hash)
        result = self.run_context()
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale example evidence", result.stderr)
        self.assertNotIn("--- knowledge/", result.stdout)

    def test_pilot_preparation_does_not_approve_other_features(self):
        for platform in ("android", "webview"):
            with self.subTest(platform=platform):
                # Test a deliberately pilot-scoped fixture; live WebView scope can
                # expand independently after explicit user authorization.
                self.edit_json("knowledge/packs.json", lambda value: value["platforms"][platform].update(
                    approved_features=["stock-search-price"]))
                result = subprocess.run([sys.executable, str(self.root / "scripts/knowledge.py"), "context",
                                         "--feature", "auth-session", "--platform", platform, "--require-ready"],
                                        cwd=self.root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("outside this platform's prepared pilot scope", result.stdout)
                self.assertNotIn("--- knowledge/", result.stdout)


if __name__ == "__main__":
    unittest.main()
