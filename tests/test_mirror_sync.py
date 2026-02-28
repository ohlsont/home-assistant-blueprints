import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_component_mirror_sync.py"
SPEC = importlib.util.spec_from_file_location("mirror_sync", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
compare_trees = MODULE.compare_trees


class MirrorSyncTests(unittest.TestCase):
    def test_compare_trees_detects_identical_content(self):
        with tempfile.TemporaryDirectory() as left_tmp, tempfile.TemporaryDirectory() as right_tmp:
            left = Path(left_tmp)
            right = Path(right_tmp)
            (left / "a.txt").write_text("same", encoding="utf-8")
            (right / "a.txt").write_text("same", encoding="utf-8")

            ok, _ = compare_trees(left, right)
            self.assertTrue(ok)

    def test_compare_trees_detects_missing_and_changed_files(self):
        with tempfile.TemporaryDirectory() as left_tmp, tempfile.TemporaryDirectory() as right_tmp:
            left = Path(left_tmp)
            right = Path(right_tmp)
            (left / "a.txt").write_text("left", encoding="utf-8")
            (right / "a.txt").write_text("right", encoding="utf-8")
            (left / "only_left.txt").write_text("x", encoding="utf-8")

            ok, details = compare_trees(left, right)
            self.assertFalse(ok)
            joined = "\n".join(details)
            self.assertIn("only_left.txt", joined)
            self.assertIn("a.txt", joined)


if __name__ == "__main__":
    unittest.main()
