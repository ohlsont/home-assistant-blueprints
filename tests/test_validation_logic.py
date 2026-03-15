import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = ROOT / "custom_components" / "blockheat" / "validation.py"
SPEC = importlib.util.spec_from_file_location("blockheat_validation", VALIDATION_PATH)
assert SPEC
assert SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_tuning_values = MODULE.validate_tuning_values


class ValidateTuningValuesTests(unittest.TestCase):
    def _base(self):
        return {
            "minutes_to_block": 240,
            "price_ignore_below": 0.6,
            "pv_ignore_above_w": 0.0,
        }

    def test_accepts_valid_values(self):
        assert validate_tuning_values(self._base()) is None

    def test_rejects_negative_intervals(self):
        payload = self._base()
        payload["minutes_to_block"] = -1
        assert validate_tuning_values(payload) == "invalid_non_negative"

    def test_rejects_negative_price_ignore(self):
        payload = self._base()
        payload["price_ignore_below"] = -0.1
        assert validate_tuning_values(payload) == "invalid_non_negative"


if __name__ == "__main__":
    unittest.main()
