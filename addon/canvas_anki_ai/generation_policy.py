from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class ConceptComplexity(str, Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class DifficultyTier(str, Enum):
    FOUNDATION = "foundation"
    UNDERSTANDING = "understanding"
    APPLICATION = "application"
    TRANSFER = "transfer"


@dataclass(frozen=True)
class CardIntent:
    name: str
    tier: DifficultyTier
    instruction: str


@dataclass(frozen=True)
class CoveragePolicy:
    name: str
    basic_intents: Tuple[CardIntent, ...]
    intermediate_intents: Tuple[CardIntent, ...]
    advanced_intents: Tuple[CardIntent, ...]

    def intents_for(self, complexity: ConceptComplexity) -> Tuple[CardIntent, ...]:
        if complexity == ConceptComplexity.BASIC:
            return self.basic_intents
        if complexity == ConceptComplexity.INTERMEDIATE:
            return self.intermediate_intents
        return self.advanced_intents


FOUNDATION = CardIntent(
    "core-recall",
    DifficultyTier.FOUNDATION,
    "Recall the concept's definition, components, or governing rule.",
)
BOUNDARIES = CardIntent(
    "boundaries",
    DifficultyTier.UNDERSTANDING,
    "Distinguish the concept from its nearest alternatives or misconceptions.",
)
MECHANISM = CardIntent(
    "mechanism",
    DifficultyTier.UNDERSTANDING,
    "Explain why the concept works or how its steps connect.",
)
REPRESENTATION = CardIntent(
    "representation",
    DifficultyTier.UNDERSTANDING,
    "Interpret the concept in another representation, such as a diagram or formula.",
)
APPLICATION = CardIntent(
    "application",
    DifficultyTier.APPLICATION,
    "Apply the concept to a concrete example similar to course work.",
)
ERROR_DIAGNOSIS = CardIntent(
    "error-diagnosis",
    DifficultyTier.APPLICATION,
    "Identify and correct a plausible mistake involving the concept.",
)
TRANSFER = CardIntent(
    "transfer",
    DifficultyTier.TRANSFER,
    "Use the concept in a novel case that requires choosing an approach.",
)


COMPREHENSIVE_ASSIGNMENT_POLICY = CoveragePolicy(
    name="comprehensive-assignment-coverage",
    basic_intents=(FOUNDATION, BOUNDARIES, APPLICATION),
    intermediate_intents=(
        FOUNDATION,
        BOUNDARIES,
        MECHANISM,
        APPLICATION,
        ERROR_DIAGNOSIS,
    ),
    advanced_intents=(
        FOUNDATION,
        BOUNDARIES,
        MECHANISM,
        REPRESENTATION,
        APPLICATION,
        ERROR_DIAGNOSIS,
        TRANSFER,
    ),
)
