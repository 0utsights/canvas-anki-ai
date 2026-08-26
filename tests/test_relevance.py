import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.relevance import ContentCategory, classify_text


class ClassifyTextTests(unittest.TestCase):
    def test_classifies_course_logistics(self) -> None:
        result = classify_text("Review the attendance and late assignment policy.")

        self.assertEqual(result.category, ContentCategory.LOGISTICS)

    def test_classifies_instructional_content(self) -> None:
        result = classify_text("Explain the mechanism that causes natural selection.")

        self.assertEqual(result.category, ContentCategory.INSTRUCTIONAL)

    def test_keeps_ambiguous_content_for_later_review(self) -> None:
        result = classify_text("Read chapter four before Monday.")

        self.assertEqual(result.category, ContentCategory.UNCERTAIN)

    def test_does_not_drop_mixed_learning_content(self) -> None:
        result = classify_text(
            "Office hours follow a comparison of mitosis and meiosis processes."
        )

        self.assertEqual(result.category, ContentCategory.UNCERTAIN)


if __name__ == "__main__":
    unittest.main()

