import tempfile
import unittest
from pathlib import Path

from tools.store import Store


class StoreTests(unittest.TestCase):
    def test_create_and_get(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.sqlite3")
            original = {"job": {"role": "Accounts Executive"}}

            created = store.create(original)
            restored = store.get(created["id"])

            self.assertEqual(restored["job"], {"role": "Accounts Executive"})
            self.assertEqual(restored["id"], created["id"])

            reopened_store = Store(Path(folder) / "test.sqlite3")
            restored = reopened_store.get(created["id"])

            self.assertEqual(restored["job"], {"role": "Accounts Executive"})
            self.assertEqual(restored["id"], created["id"])

    def test_save_updates_existing_run(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.sqlite3")
            created = store.create({"decision": None})

            created["decision"] = "shortlist"
            store.save(created["id"], created)

            restored = store.get(created["id"])
            self.assertEqual(restored["decision"], "shortlist")

    def test_get_missing_run_raises_error(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.sqlite3")

            with self.assertRaises(KeyError):
                store.get("missing-run")
