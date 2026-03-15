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
            "control_min_c": 10.0,
            "control_max_c": 26.0,
            "boost_slope_c": 5.0,
            "saving_helper_write_delta_c": 0.05,
            "comfort_helper_write_delta_c": 0.05,
            "final_helper_write_delta_c": 0.05,
            "control_write_delta_c": 0.2,
            "min_toggle_interval_min": 15,
            "minutes_to_block": 240,
        }

    def test_accepts_valid_values(self):
        assert validate_tuning_values(self._base()) is None

    def test_rejects_inverted_control_range(self):
        payload = self._base()
        payload["control_min_c"] = 27.0
        payload["control_max_c"] = 26.0
        assert validate_tuning_values(payload) == "invalid_control_range"

    def test_rejects_non_positive_boost_slope(self):
        payload = self._base()
        payload["boost_slope_c"] = 0
        assert validate_tuning_values(payload) == "invalid_boost_slope"

    def test_rejects_negative_deltas(self):
        payload = self._base()
        payload["control_write_delta_c"] = -0.1
        assert validate_tuning_values(payload) == "invalid_non_negative"

    def test_rejects_negative_intervals(self):
        payload = self._base()
        payload["minutes_to_block"] = -1
        assert validate_tuning_values(payload) == "invalid_non_negative"


if __name__ == "__main__":
    unittest.main()
