from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple


class SourceKind(str, Enum):
    PAGE = "page"
    PDF = "pdf"
    SLIDES = "slides"
    SYLLABUS = "syllabus"
    ASSIGNMENT = "assignment"
    OTHER = "other"


@dataclass(frozen=True)
class SourceDocument:
    canvas_course_id: int
    canvas_item_id: str
    course_name: str
    title: str
    kind: SourceKind
    text: str
    source_url: str
    module_name: Optional[str] = None
    available_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class SourceReference:
    document_id: str
    title: str
    location: str
    excerpt: str
    source_url: str


@dataclass(frozen=True)
class DraftCard:
    front: str
    back: str
    course_name: str
    references: Tuple[SourceReference, ...]
    tags: Tuple[str, ...] = field(default_factory=tuple)
    confidence: Optional[float] = None

