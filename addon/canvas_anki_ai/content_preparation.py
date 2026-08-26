import hashlib
import re
from dataclasses import replace
from typing import Iterable, List, Sequence, Tuple

from .models import ExtractedContent, ExtractedSection
from .relevance import ContentCategory, classify_text
from .study_models import ContentChunk, PreparedCorpus, SourceLocator


DEFAULT_MAX_CHARS = 1800
DEFAULT_MIN_CHARS = 350
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def prepare_corpus(
    contents: Iterable[ExtractedContent],
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> PreparedCorpus:
    chunks = []
    for content in contents:
        chunks.extend(chunk_content(content, max_chars, min_chars))

    included = []
    excluded = []
    for chunk in chunks:
        classification = classify_text(chunk.text)
        classified = replace(
            chunk,
            category=classification.category,
            relevance_reasons=classification.matched_terms,
        )
        if classification.category == ContentCategory.LOGISTICS:
            excluded.append(classified)
        else:
            included.append(classified)
    return PreparedCorpus(tuple(included), tuple(excluded))


def chunk_content(
    content: ExtractedContent,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> Tuple[ContentChunk, ...]:
    if min_chars <= 0 or max_chars < min_chars:
        raise ValueError("Chunk sizes must satisfy 0 < min_chars <= max_chars")

    chunks = []
    ordinal = 0
    for section in content.sections:
        locator = SourceLocator(
            course_id=content.payload.course_id,
            source_id=content.payload.source_id,
            source_title=content.payload.title,
            source_kind=content.payload.kind,
            location=section.location,
            source_url=content.payload.source_url,
        )
        for text in _section_chunks(section, max_chars, min_chars):
            ordinal += 1
            chunks.append(
                ContentChunk(
                    chunk_id=_chunk_id(locator, ordinal, text),
                    text=text,
                    locator=locator,
                    ordinal=ordinal,
                    estimated_tokens=max(1, (len(text) + 3) // 4),
                    category=ContentCategory.UNCERTAIN,
                    relevance_reasons=(),
                )
            )
    return tuple(chunks)


def _section_chunks(
    section: ExtractedSection, max_chars: int, min_chars: int
) -> Tuple[str, ...]:
    units = []
    for block in section.text.splitlines():
        normalized = " ".join(block.split())
        if normalized:
            units.extend(_split_long_unit(normalized, max_chars))
    return _pack_units(units, max_chars, min_chars)


def _split_long_unit(value: str, max_chars: int) -> Tuple[str, ...]:
    if len(value) <= max_chars:
        return (value,)
    sentences = SENTENCE_BOUNDARY.split(value)
    if len(sentences) == 1:
        return _hard_wrap(value, max_chars)
    units = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            units.append(sentence)
        else:
            units.extend(_hard_wrap(sentence, max_chars))
    return tuple(units)


def _hard_wrap(value: str, max_chars: int) -> Tuple[str, ...]:
    words = [
        part
        for word in value.split()
        for part in (
            tuple(word[index : index + max_chars] for index in range(0, len(word), max_chars))
            if len(word) > max_chars
            else (word,)
        )
    ]
    chunks: List[str] = []
    current: List[str] = []
    current_length = 0
    for word in words:
        additional = len(word) + (1 if current else 0)
        if current and current_length + additional > max_chars:
            chunks.append(" ".join(current))
            current = []
            current_length = 0
        current.append(word)
        current_length += len(word) + (1 if len(current) > 1 else 0)
    if current:
        chunks.append(" ".join(current))
    return tuple(chunks)


def _pack_units(
    units: Sequence[str], max_chars: int, min_chars: int
) -> Tuple[str, ...]:
    packed: List[str] = []
    current: List[str] = []
    current_length = 0
    for unit in units:
        additional = len(unit) + (1 if current else 0)
        if current and current_length + additional > max_chars:
            packed.append("\n".join(current))
            current = []
            current_length = 0
        current.append(unit)
        current_length += len(unit) + (1 if len(current) > 1 else 0)

    if current:
        tail = "\n".join(current)
        if packed and len(tail) < min_chars and len(packed[-1]) + 1 + len(tail) <= max_chars:
            packed[-1] += "\n" + tail
        else:
            packed.append(tail)
    return tuple(packed)


def _chunk_id(locator: SourceLocator, ordinal: int, text: str) -> str:
    identity = (
        f"{locator.course_id}|{locator.source_id}|{locator.location}|{ordinal}|{text}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
