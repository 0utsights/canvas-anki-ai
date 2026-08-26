import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.ai_contract import (
    AIContractError,
    StructuredResponse,
    analyze_concepts,
    generate_cards,
)
from canvas_anki_ai.content_preparation import prepare_corpus
from canvas_anki_ai.models import (
    ContentPayload,
    ExtractedContent,
    ExtractedSection,
    SourceKind,
)


class FakeProvider:
    provider_name = "fake"

    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.tasks = []

    def complete_json(self, task):
        self.tasks.append(task)
        return StructuredResponse(self.responses.pop(0), "fake-model")


def corpus():
    page = ExtractedContent(
        ContentPayload(
            1,
            "page-1",
            "Cell Cycle Notes",
            SourceKind.PAGE,
            "text/html",
            b"",
            "https://example.edu/page",
        ),
        (ExtractedSection("Page", "Explain the process of mitosis and its phases."),),
    )
    assignment = ExtractedContent(
        ContentPayload(
            1,
            "assignment-1",
            "Mitosis Problems",
            SourceKind.ASSIGNMENT,
            "text/html",
            b"",
            "https://example.edu/assignment",
        ),
        (ExtractedSection("Assignment", "Analyze how an error in mitosis affects daughter cells."),),
    )
    return prepare_corpus((page, assignment), max_chars=500, min_chars=1)


class AIContractTests(unittest.TestCase):
    def test_builds_coverage_matrix_from_validated_concepts(self) -> None:
        prepared = corpus()
        page_id, assignment_id = [chunk.chunk_id for chunk in prepared.included]
        provider = FakeProvider(
            [
                {
                    "concepts": [
                        {
                            "name": "Mitosis",
                            "summary": "Nuclear division through ordered phases.",
                            "complexity": "intermediate",
                            "supporting_chunk_ids": [page_id, assignment_id],
                            "assignment_chunk_ids": [assignment_id],
                        }
                    ]
                }
            ]
        )

        matrix = analyze_concepts(provider, prepared)

        self.assertEqual(len(matrix.concepts), 1)
        self.assertEqual(len(matrix.targets), 5)
        self.assertEqual(provider.tasks[0].task_name, "analyze-course-concepts")

    def test_rejects_unknown_source_chunk(self) -> None:
        prepared = corpus()
        provider = FakeProvider(
            [
                {
                    "concepts": [
                        {
                            "name": "Mitosis",
                            "summary": "Cell division.",
                            "complexity": "basic",
                            "supporting_chunk_ids": ["invented"],
                            "assignment_chunk_ids": [],
                        }
                    ]
                }
            ]
        )

        with self.assertRaisesRegex(AIContractError, "unknown chunk"):
            analyze_concepts(provider, prepared)

    def test_accepts_explicitly_unsupported_card_target(self) -> None:
        prepared = corpus()
        page_id, assignment_id = [chunk.chunk_id for chunk in prepared.included]
        provider = FakeProvider(
            [
                {
                    "concepts": [
                        {
                            "name": "Mitosis",
                            "summary": "Cell division.",
                            "complexity": "basic",
                            "supporting_chunk_ids": [page_id, assignment_id],
                            "assignment_chunk_ids": [assignment_id],
                        }
                    ]
                }
            ]
        )
        matrix = analyze_concepts(provider, prepared)
        card_response = {"cards": [], "unsupported_targets": []}
        for index, target in enumerate(matrix.targets):
            if index == len(matrix.targets) - 1:
                card_response["unsupported_targets"].append(
                    {
                        "concept_id": target.concept_id,
                        "intent_name": target.intent_name,
                        "reason": "The supplied sources lack a suitable application example.",
                    }
                )
            else:
                card_response["cards"].append(
                    {
                        "concept_id": target.concept_id,
                        "intent_name": target.intent_name,
                        "difficulty": target.difficulty.value,
                        "front": f"Question for {target.intent_name}?",
                        "back": "Grounded answer.",
                        "source_chunk_ids": [page_id],
                    }
                )
        card_provider = FakeProvider([card_response])

        batch = generate_cards(card_provider, prepared, matrix)

        self.assertEqual(len(batch.cards), 2)
        self.assertEqual(len(batch.unsupported_targets), 1)


if __name__ == "__main__":
    unittest.main()
