from typing import Iterable

from .generation_policy import COMPREHENSIVE_ASSIGNMENT_POLICY, CoveragePolicy
from .study_models import CoverageMatrix, CoverageTarget, StudyConcept


def build_coverage_matrix(
    concepts: Iterable[StudyConcept],
    policy: CoveragePolicy = COMPREHENSIVE_ASSIGNMENT_POLICY,
) -> CoverageMatrix:
    concept_tuple = tuple(concepts)
    targets = tuple(
        CoverageTarget(
            concept_id=concept.concept_id,
            intent_name=intent.name,
            difficulty=intent.tier,
            instruction=intent.instruction,
            supporting_chunk_ids=concept.supporting_chunk_ids,
        )
        for concept in concept_tuple
        for intent in policy.intents_for(concept.complexity)
    )
    return CoverageMatrix(concept_tuple, targets)
