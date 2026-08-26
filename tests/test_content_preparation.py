import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.content_preparation import chunk_content, prepare_corpus
from canvas_anki_ai.models import (
    ContentPayload,
    ExtractedContent,
    ExtractedSection,
    SourceKind,
)
from canvas_anki_ai.relevance import ContentCategory


def extracted(kind=SourceKind.PAGE, sections=None):
    payload = ContentPayload(
        1,
        "source-1",
        "Biology Lesson",
        kind,
        "text/html",
        b"",
        "https://example.edu/lesson",
    )
    return ExtractedContent(payload, tuple(sections or ()))


class ContentPreparationTests(unittest.TestCase):
    def test_preserves_source_location_and_stable_chunk_id(self) -> None:
        content = extracted(
            sections=(ExtractedSection("Slide 4", "Explain how DNA replication works."),)
        )

        first = chunk_content(content, max_chars=100, min_chars=1)
        second = chunk_content(content, max_chars=100, min_chars=1)

        self.assertEqual(first[0].chunk_id, second[0].chunk_id)
        self.assertEqual(first[0].locator.location, "Slide 4")

    def test_splits_long_content_within_limit(self) -> None:
        text = " ".join(["Replication produces a complementary strand."] * 20)
        content = extracted(sections=(ExtractedSection("Page 1", text),))

        chunks = chunk_content(content, max_chars=180, min_chars=40)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.text) <= 180 for chunk in chunks))

    def test_splits_single_overlong_token(self) -> None:
        content = extracted(
            sections=(ExtractedSection("Page 1", "x" * 401),)
        )

        chunks = chunk_content(content, max_chars=100, min_chars=1)

        self.assertEqual(len(chunks), 5)
        self.assertTrue(all(len(chunk.text) <= 100 for chunk in chunks))

    def test_excludes_only_high_confidence_logistics(self) -> None:
        content = extracted(
            SourceKind.SYLLABUS,
            (
                ExtractedSection(
                    "Policy",
                    "Attendance is required. Late assignments follow the grading policy.",
                ),
                ExtractedSection(
                    "Learning outcomes",
                    "Explain the mechanism that causes natural selection.",
                ),
                ExtractedSection("Reminder", "Read chapter four before Monday."),
            ),
        )

        corpus = prepare_corpus(content for content in (content,))

        self.assertEqual(len(corpus.excluded), 1)
        self.assertEqual(corpus.excluded[0].category, ContentCategory.LOGISTICS)
        self.assertEqual(len(corpus.included), 2)
        self.assertIn(ContentCategory.UNCERTAIN, {chunk.category for chunk in corpus.included})


if __name__ == "__main__":
    unittest.main()
