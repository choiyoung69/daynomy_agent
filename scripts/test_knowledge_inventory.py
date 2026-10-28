#!/usr/bin/env python3
"""Check that changed, missing and newly added source routes cannot silently pass."""

from pathlib import Path
import shutil
import tempfile
import unittest

from knowledge_inventory import BASE, ROOT, build_inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="knowledge-inventory-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "spec").mkdir()
        shutil.copy2(ROOT / "spec/service.md", self.root / "spec/service.md")
        for source in (ROOT / BASE).rglob("*Controller*.java"):
            if "league" in source.relative_to(ROOT / BASE).parts:
                continue
            target = self.root / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def test_reference_inventory(self):
        inventory = build_inventory(self.root)
        self.assertEqual((inventory["controller_count"], inventory["handler_count"], inventory["expanded_route_count"]), (31, 81, 89))

    def test_changed_source_route_is_rejected(self):
        path = self.root / BASE / "auth/controller/AuthController.java"
        path.write_text(path.read_text().replace('"/api/auth"', '"/api/changed-auth"'))
        with self.assertRaisesRegex(ValueError, "mapping mismatch"):
            build_inventory(self.root)

    def test_new_controller_is_rejected(self):
        path = self.root / BASE / "AddedController.java"
        path.write_text('class AddedController { @GetMapping("/added") void get() {} }')
        with self.assertRaisesRegex(ValueError, "controller set differs"):
            build_inventory(self.root)

    def test_v2_controller_removal_is_rejected(self):
        (self.root / BASE / "portfolio/v2/controller/PortfolioTransactionControllerV2.java").unlink()
        with self.assertRaisesRegex(ValueError, "controller set differs"):
            build_inventory(self.root)


if __name__ == "__main__":
    unittest.main()
