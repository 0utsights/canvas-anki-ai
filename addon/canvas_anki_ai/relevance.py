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
    logistics_score: int = 0
    instructional_score: int = 0


LOGISTICS_PATTERNS = (
    r"\battendance\b",
    r"\boffice hours?\b",
    r"\bgrading (?:policy|scale)\b",
    r"\blate (?:work|assignment|submission)s?\b",
    r"\bacademic (?:honesty|integrity)\b",
    r"\bcontact (?:the )?instructor\b",
    r"\bsubmission instructions?\b",
    r"\bclassroom polic(?:y|ies)\b",
    r"\b(?:worth|total(?:ing)?) \d+ points?\b",
    r"\bdue (?:on|by|date)\b",
    r"\bsubmit(?:ted|ting)? (?:to|through|via|your)\b",
    r"\bemail (?:me|the instructor|your)\b",
    r"\bgrade(?:d|s)?\b",
    r"\bmake-?up (?:exam|quiz|work)\b",
    r"\bdisability accommodations?\b",
    r"\btechnical support\b",
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
    r"\banaly[sz](?:e|es|ing)\b",
    r"\bcalculate\b",
    r"\bderive\b",
    r"\bidentify\b",
    r"\bdescribe\b",
    r"\brelationship between\b",
    r"\bfor example\b",
    r"\btherefore\b",
)


def _matches(text: str, patterns: Iterable[str]) -> Tuple[str, ...]:
    return tuple(pattern for pattern in patterns if re.search(pattern, text, re.IGNORECASE))


def classify_text(text: str) -> Classification:
    logistics = _matches(text, LOGISTICS_PATTERNS)
    instructional = _matches(text, INSTRUCTIONAL_PATTERNS)
    logistics_score = len(logistics)
    instructional_score = len(instructional)

    if logistics_score >= 2 and instructional_score == 0:
        return Classification(
            ContentCategory.LOGISTICS,
            logistics,
            logistics_score,
            instructional_score,
        )
    if instructional_score >= 1 and logistics_score == 0:
        return Classification(
            ContentCategory.INSTRUCTIONAL,
            instructional,
            logistics_score,
            instructional_score,
        )
    return Classification(
        ContentCategory.UNCERTAIN,
        logistics + instructional,
        logistics_score,
        instructional_score,
    )
