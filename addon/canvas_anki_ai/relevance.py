import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple


class ContentCategory(str, Enum):
    INSTRUCTIONAL = "instructional"
    LOGISTICS = "logistics"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class Classification:
    category: ContentCategory
    matched_terms: Tuple[str, ...]


LOGISTICS_PATTERNS = (
    r"\battendance\b",
    r"\boffice hours?\b",
    r"\bgrading (?:policy|scale)\b",
    r"\blate (?:work|assignment|submission)s?\b",
    r"\bacademic (?:honesty|integrity)\b",
    r"\bcontact (?:the )?instructor\b",
    r"\bsubmission instructions?\b",
    r"\bclassroom polic(?:y|ies)\b",
)

INSTRUCTIONAL_PATTERNS = (
    r"\bdefine\b",
    r"\bexplains?\b",
    r"\bcauses?\b",
    r"\bmechanisms?\b",
    r"\btheor(?:y|ies)\b",
    r"\bformulas?\b",
    r"\bcompare\b",
    r"\bprocess(?:es)?\b",
)


def _matches(text: str, patterns: Iterable[str]) -> Tuple[str, ...]:
    return tuple(pattern for pattern in patterns if re.search(pattern, text, re.IGNORECASE))


def classify_text(text: str) -> Classification:
    logistics = _matches(text, LOGISTICS_PATTERNS)
    instructional = _matches(text, INSTRUCTIONAL_PATTERNS)

    if logistics and not instructional:
        return Classification(ContentCategory.LOGISTICS, logistics)
    if instructional and not logistics:
        return Classification(ContentCategory.INSTRUCTIONAL, instructional)
    return Classification(ContentCategory.UNCERTAIN, logistics + instructional)

