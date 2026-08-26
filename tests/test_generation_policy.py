import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.generation_policy import (
    COMPREHENSIVE_ASSIGNMENT_POLICY,
    ConceptComplexity,
    DifficultyTier,
)


class CoveragePolicyTests(unittest.TestCase):
    def test_scales_card_variety_with_concept_complexity(self) -> None:
        basic = COMPREHENSIVE_ASSIGNMENT_POLICY.intents_for(ConceptComplexity.BASIC)
        intermediate = COMPREHENSIVE_ASSIGNMENT_POLICY.intents_for(
            ConceptComplexity.INTERMEDIATE
        )
        advanced = COMPREHENSIVE_ASSIGNMENT_POLICY.intents_for(
            ConceptComplexity.ADVANCED
        )

        self.assertEqual((len(basic), len(intermediate), len(advanced)), (3, 5, 7))

    def test_advanced_concepts_span_all_difficulty_tiers(self) -> None:
        intents = COMPREHENSIVE_ASSIGNMENT_POLICY.intents_for(
            ConceptComplexity.ADVANCED
        )

        self.assertEqual(
            {intent.tier for intent in intents},
            set(DifficultyTier),
        )
