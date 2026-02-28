import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = ROOT / "custom_components" / "blockheat" / "validation.py"
SPEC = importlib.util.spec_from_file_location("blockheat_validation", VALIDATION_PATH)
assert SPEC and SPEC.loader
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
            "electric_fallback_delta_c": 0.5,
            "release_delta_c": 0.1,
            "electric_fallback_minutes": 30,
            "electric_fallback_cooldown_minutes": 60,
            "min_toggle_interval_min": 15,
            "minutes_to_block": 240,
            "floor_min_switch_interval_min": 15,
        }

    def test_accepts_valid_values(self):
        self.assertIsNone(validate_tuning_values(self._base()))

    def test_rejects_inverted_control_range(self):
        payload = self._base()
        payload["control_min_c"] = 27.0
        payload["control_max_c"] = 26.0
        self.assertEqual(validate_tuning_values(payload), "invalid_control_range")

    def test_rejects_non_positive_boost_slope(self):
        payload = self._base()
        payload["boost_slope_c"] = 0
        self.assertEqual(validate_tuning_values(payload), "invalid_boost_slope")

    def test_rejects_negative_deltas(self):
        payload = self._base()
        payload["control_write_delta_c"] = -0.1
        self.assertEqual(validate_tuning_values(payload), "invalid_non_negative")

    def test_rejects_negative_intervals(self):
        payload = self._base()
        payload["electric_fallback_minutes"] = -1
        self.assertEqual(validate_tuning_values(payload), "invalid_non_negative")


if __name__ == "__main__":
    unittest.main()
