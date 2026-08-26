import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Protocol, Sequence, Tuple

from .coverage import build_coverage_matrix
from .generation_policy import ConceptComplexity, DifficultyTier
from .models import SourceKind
from .study_models import (
    CoverageMatrix,
    GeneratedCard,
    GeneratedCardBatch,
    PreparedCorpus,
    StudyConcept,
    UnsupportedCoverageTarget,
)


class AIContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class StructuredTask:
    task_name: str
    instructions: str
    input_data: Mapping[str, Any]
    output_schema: Mapping[str, Any]


@dataclass(frozen=True)
class StructuredResponse:
    data: Mapping[str, Any]
    model_name: str


class StructuredAIProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    def complete_json(self, task: StructuredTask) -> StructuredResponse:
        ...


CONCEPT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "required": ["concepts"],
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "summary",
                    "complexity",
                    "supporting_chunk_ids",
                    "assignment_chunk_ids",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "complexity": {
                        "type": "string",
                        "enum": ["basic", "intermediate", "advanced"],
                    },
                    "supporting_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "assignment_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "additionalProperties": False,
            },
        }
    },
    "additionalProperties": False,
}

CARD_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "required": ["cards", "unsupported_targets"],
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "concept_id",
                    "intent_name",
                    "difficulty",
                    "front",
                    "back",
                    "source_chunk_ids",
                ],
                "properties": {
                    "concept_id": {"type": "string"},
                    "intent_name": {"type": "string"},
                    "difficulty": {
                        "type": "string",
                        "enum": [
                            "foundation",
                            "understanding",
                            "application",
                            "transfer",
                        ],
                    },
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                    "source_chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "additionalProperties": False,
            },
        },
        "unsupported_targets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["concept_id", "intent_name", "reason"],
                "properties": {
                    "concept_id": {"type": "string"},
                    "intent_name": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def analyze_concepts(
    provider: StructuredAIProvider, corpus: PreparedCorpus
) -> CoverageMatrix:
    if not corpus.included:
        raise AIContractError("No instructional content is available for concept analysis")
    task = StructuredTask(
        task_name="analyze-course-concepts",
        instructions=(
            "Identify every independently testable instructional concept. Ignore course logistics. "
            "Assignments indicate emphasis, but concept summaries must be supported by source chunks. "
            "Use only supplied chunk IDs and return JSON matching the schema."
        ),
        input_data={"chunks": [_chunk_data(chunk) for chunk in corpus.included]},
        output_schema=CONCEPT_SCHEMA,
    )
    response = provider.complete_json(task)
    concepts = _parse_concepts(response.data, corpus)
    return build_coverage_matrix(concepts)


def generate_cards(
    provider: StructuredAIProvider,
    corpus: PreparedCorpus,
    matrix: CoverageMatrix,
) -> GeneratedCardBatch:
    chunks = {chunk.chunk_id: chunk for chunk in corpus.included}
    task = StructuredTask(
        task_name="generate-grounded-cards",
        instructions=(
            "Generate one atomic card for every coverage target. Vary cognitive difficulty according "
            "to the target. Every answer must be fully supported by cited source chunks. Do not invent "
            "facts, combine unrelated concepts, or produce course-logistics cards. If the supplied "
            "evidence cannot support a target, return it in unsupported_targets with a reason."
        ),
        input_data={
            "chunks": [_chunk_data(chunk) for chunk in corpus.included],
            "concepts": [
                {
                    "concept_id": concept.concept_id,
                    "name": concept.name,
                    "summary": concept.summary,
                    "complexity": concept.complexity.value,
                }
                for concept in matrix.concepts
            ],
            "targets": [
                {
                    "concept_id": target.concept_id,
                    "intent_name": target.intent_name,
                    "difficulty": target.difficulty.value,
                    "instruction": target.instruction,
                    "supporting_chunk_ids": list(target.supporting_chunk_ids),
                }
                for target in matrix.targets
            ],
        },
        output_schema=CARD_SCHEMA,
    )
    response = provider.complete_json(task)
    cards, unsupported = _parse_cards(response.data, matrix, tuple(chunks))
    return GeneratedCardBatch(
        cards, unsupported, provider.provider_name, response.model_name
    )


def _parse_concepts(
    data: Mapping[str, Any], corpus: PreparedCorpus
) -> Tuple[StudyConcept, ...]:
    raw_concepts = data.get("concepts")
    if not isinstance(raw_concepts, list):
        raise AIContractError("AI concept response must contain a concepts array")
    chunks = {chunk.chunk_id: chunk for chunk in corpus.included}
    concepts = []
    seen_names = set()
    for raw in raw_concepts:
        if not isinstance(raw, dict):
            raise AIContractError("Every concept must be an object")
        name = _required_text(raw, "name")
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            raise AIContractError(f"Duplicate concept: {name}")
        seen_names.add(normalized_name)
        summary = _required_text(raw, "summary")
        try:
            complexity = ConceptComplexity(_required_text(raw, "complexity"))
        except ValueError as error:
            raise AIContractError(f"Invalid complexity for {name}") from error
        supporting = _chunk_ids(raw, "supporting_chunk_ids", chunks)
        if not supporting:
            raise AIContractError(f"Concept has no supporting evidence: {name}")
        assignment_ids = _chunk_ids(raw, "assignment_chunk_ids", chunks, allow_empty=True)
        if any(chunks[chunk_id].locator.source_kind != SourceKind.ASSIGNMENT for chunk_id in assignment_ids):
            raise AIContractError(f"Concept cites a non-assignment as assignment evidence: {name}")
        if not set(assignment_ids).issubset(supporting):
            raise AIContractError(f"Assignment evidence is not supporting evidence: {name}")
        concept_id = hashlib.sha256(
            f"{normalized_name}|{'|'.join(supporting)}".encode("utf-8")
        ).hexdigest()[:20]
        concepts.append(
            StudyConcept(
                concept_id,
                name,
                summary,
                complexity,
                supporting,
                assignment_ids,
            )
        )
    return tuple(concepts)


def _parse_cards(
    data: Mapping[str, Any], matrix: CoverageMatrix, valid_chunk_ids: Sequence[str]
) -> Tuple[Tuple[GeneratedCard, ...], Tuple[UnsupportedCoverageTarget, ...]]:
    raw_cards = data.get("cards")
    if not isinstance(raw_cards, list):
        raise AIContractError("AI card response must contain a cards array")
    targets = {
        (target.concept_id, target.intent_name): target for target in matrix.targets
    }
    valid_chunks = set(valid_chunk_ids)
    cards = []
    seen_targets = set()
    for raw in raw_cards:
        if not isinstance(raw, dict):
            raise AIContractError("Every card must be an object")
        concept_id = _required_text(raw, "concept_id")
        intent_name = _required_text(raw, "intent_name")
        target_key = (concept_id, intent_name)
        if target_key not in targets:
            raise AIContractError("Card references an unknown coverage target")
        if target_key in seen_targets:
            raise AIContractError("AI returned duplicate cards for a coverage target")
        seen_targets.add(target_key)
        try:
            difficulty = DifficultyTier(_required_text(raw, "difficulty"))
        except ValueError as error:
            raise AIContractError("Card has an invalid difficulty") from error
        if difficulty != targets[target_key].difficulty:
            raise AIContractError("Card difficulty does not match its coverage target")
        source_ids = _chunk_ids(raw, "source_chunk_ids", valid_chunks)
        if not source_ids:
            raise AIContractError("Card has no source evidence")
        if not set(source_ids).issubset(targets[target_key].supporting_chunk_ids):
            raise AIContractError("Card cites evidence outside its concept")
        front = _required_text(raw, "front")
        back = _required_text(raw, "back")
        card_id = hashlib.sha256(
            f"{concept_id}|{intent_name}|{front}|{back}".encode("utf-8")
        ).hexdigest()[:20]
        cards.append(
            GeneratedCard(
                card_id,
                concept_id,
                intent_name,
                difficulty,
                front,
                back,
                source_ids,
            )
        )
    raw_unsupported = data.get("unsupported_targets")
    if not isinstance(raw_unsupported, list):
        raise AIContractError("AI card response must contain unsupported_targets")
    unsupported = []
    for raw in raw_unsupported:
        if not isinstance(raw, dict):
            raise AIContractError("Every unsupported target must be an object")
        concept_id = _required_text(raw, "concept_id")
        intent_name = _required_text(raw, "intent_name")
        target_key = (concept_id, intent_name)
        if target_key not in targets:
            raise AIContractError("AI marked an unknown coverage target unsupported")
        if target_key in seen_targets:
            raise AIContractError("Coverage target appears more than once")
        seen_targets.add(target_key)
        unsupported.append(
            UnsupportedCoverageTarget(
                concept_id,
                intent_name,
                _required_text(raw, "reason"),
            )
        )

    missing = set(targets) - seen_targets
    if missing:
        raise AIContractError(f"AI omitted {len(missing)} coverage targets")
    return tuple(cards), tuple(unsupported)


def _chunk_data(chunk) -> Dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "source_title": chunk.locator.source_title,
        "source_kind": chunk.locator.source_kind.value,
        "location": chunk.locator.location,
    }


def _required_text(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise AIContractError(f"AI response requires non-empty {key}")
    return result.strip()


def _chunk_ids(
    value: Mapping[str, Any],
    key: str,
    valid_chunks,
    allow_empty: bool = False,
) -> Tuple[str, ...]:
    raw_ids = value.get(key)
    if not isinstance(raw_ids, list) or any(not isinstance(item, str) for item in raw_ids):
        raise AIContractError(f"AI response requires a string array for {key}")
    result = tuple(sorted(set(raw_ids)))
    if not allow_empty and not result:
        raise AIContractError(f"AI response requires at least one {key}")
    unknown = set(result) - set(valid_chunks)
    if unknown:
        raise AIContractError(f"AI referenced {len(unknown)} unknown chunk IDs")
    return result
