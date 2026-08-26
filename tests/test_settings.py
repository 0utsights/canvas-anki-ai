import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.settings import AddonSettings


class AddonSettingsTests(unittest.TestCase):
    def test_sanitizes_and_deduplicates_course_ids(self) -> None:
        settings = AddonSettings.from_mapping(
            {
                "canvas_base_url": "https://school.instructure.com",
                "selected_course_ids": [3, "4", True, 3, 1],
            }
        )

        self.assertEqual(settings.selected_course_ids, (1, 3))

    def test_round_trips_supported_settings(self) -> None:
        settings = AddonSettings("https://school.instructure.com", (1, 3))

        self.assertEqual(
            AddonSettings.from_mapping(settings.to_mapping()),
            settings,
        )


if __name__ == "__main__":
    unittest.main()
