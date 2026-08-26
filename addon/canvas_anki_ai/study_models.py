from dataclasses import dataclass
from typing import Tuple

from .generation_policy import ConceptComplexity, DifficultyTier
from .models import SourceKind
from .relevance import ContentCategory


@dataclass(frozen=True)
class SourceLocator:
    course_id: int
    source_id: str
    source_title: str
    source_kind: SourceKind
    location: str
    source_url: str


@dataclass(frozen=True)
class ContentChunk:
    chunk_id: str
    text: str
    locator: SourceLocator
    ordinal: int
    estimated_tokens: int
    category: ContentCategory
    relevance_reasons: Tuple[str, ...]


@dataclass(frozen=True)
class PreparedCorpus:
    included: Tuple[ContentChunk, ...]
    excluded: Tuple[ContentChunk, ...]


@dataclass(frozen=True)
class StudyConcept:
    concept_id: str
    name: str
    summary: str
    complexity: ConceptComplexity
    supporting_chunk_ids: Tuple[str, ...]
    assignment_chunk_ids: Tuple[str, ...]


@dataclass(frozen=True)
class CoverageTarget:
    concept_id: str
    intent_name: str
    difficulty: DifficultyTier
    instruction: str
    supporting_chunk_ids: Tuple[str, ...]


@dataclass(frozen=True)
class CoverageMatrix:
    concepts: Tuple[StudyConcept, ...]
    targets: Tuple[CoverageTarget, ...]


@dataclass(frozen=True)
class GeneratedCard:
    card_id: str
    concept_id: str
    intent_name: str
    difficulty: DifficultyTier
    front: str
    back: str
    source_chunk_ids: Tuple[str, ...]


@dataclass(frozen=True)
class UnsupportedCoverageTarget:
    concept_id: str
    intent_name: str
    reason: str


@dataclass(frozen=True)
class GeneratedCardBatch:
    cards: Tuple[GeneratedCard, ...]
    unsupported_targets: Tuple[UnsupportedCoverageTarget, ...]
    provider_name: str
    model_name: str
