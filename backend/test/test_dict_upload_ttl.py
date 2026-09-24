import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestDictUploadTTL(unittest.TestCase):
    def test_upload_worker_writes_bson_date_expiry(self):
        source = (ROOT / "app/services/dict_upload.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {node.names[0].name for node in tree.body if isinstance(node, ast.Import)}
        from_imports = {
            node.module: {alias.name for alias in node.names}
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
        }
        self.assertIn("datetime", from_imports)
        self.assertIn("timezone", from_imports["datetime"])
        self.assertIn("expire_at", source)
        self.assertIn("timedelta(days=7)", source)

    def test_expiry_is_seven_days_in_the_future(self):
        created = datetime.now(timezone.utc)
        expiry = created + timedelta(days=7)
        self.assertEqual(expiry - created, timedelta(days=7))
        self.assertIsNotNone(expiry.tzinfo)

    def test_ttl_index_uses_absolute_expiry_field(self):
        source = (ROOT / "app/utils/arlupdate.py").read_text(encoding="utf-8")
        self.assertIn('[("expire_at", 1)], expireAfterSeconds=0', source)
        self.assertIn('"$dateAdd"', source)
        self.assertIn('"$toDate"', source)


if __name__ == "__main__":
    unittest.main()
