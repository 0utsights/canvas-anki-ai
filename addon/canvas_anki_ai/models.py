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
class CanvasCourse:
    course_id: int
    name: str
    course_code: str


class CanvasItemKind(str, Enum):
    PAGE = "Page"
    FILE = "File"
    ASSIGNMENT = "Assignment"
    QUIZ = "Quiz"
    DISCUSSION = "Discussion"
    EXTERNAL_URL = "ExternalUrl"
    EXTERNAL_TOOL = "ExternalTool"
    OTHER = "Other"

    @classmethod
    def from_canvas(cls, value: object) -> "CanvasItemKind":
        try:
            return cls(str(value))
        except ValueError:
            return cls.OTHER


@dataclass(frozen=True)
class CanvasModuleItem:
    course_id: int
    module_id: int
    item_id: int
    content_id: Optional[int]
    title: str
    kind: CanvasItemKind
    position: int
    module_name: str
    module_position: int
    module_state: str
    api_url: Optional[str] = None
    html_url: Optional[str] = None
    due_at: Optional[datetime] = None
    unlock_at: Optional[datetime] = None
    lock_at: Optional[datetime] = None
    module_unlock_at: Optional[datetime] = None
    published: bool = True


@dataclass(frozen=True)
class CanvasModule:
    course_id: int
    module_id: int
    name: str
    position: int
    state: str
    unlock_at: Optional[datetime]
    items: Tuple[CanvasModuleItem, ...]


@dataclass(frozen=True)
class ContentPayload:
    course_id: int
    source_id: str
    title: str
    kind: SourceKind
    media_type: str
    body: bytes
    source_url: str
    module_name: Optional[str] = None
    due_at: Optional[datetime] = None


@dataclass(frozen=True)
class ExtractedSection:
    location: str
    text: str


@dataclass(frozen=True)
class ExtractedContent:
    payload: ContentPayload
    sections: Tuple[ExtractedSection, ...]


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
