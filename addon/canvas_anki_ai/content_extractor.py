import re
from html.parser import HTMLParser
from io import BytesIO
from pathlib import PurePosixPath
from typing import Iterable, List, Tuple
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from .models import ContentPayload, ExtractedContent, ExtractedSection, SourceKind


MAX_EXPANDED_ARCHIVE_BYTES = 200 * 1024 * 1024
BLOCK_TAGS = {
    "article",
    "blockquote",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "section",
    "table",
    "tr",
}


class ContentExtractionError(RuntimeError):
    pass


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        if tag in BLOCK_TAGS or tag == "br":
            self.parts.append("\n")
        if tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.parts.append(f" [Image: {alt}] ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if not self.ignored_depth and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def extract_content(payload: ContentPayload) -> ExtractedContent:
    title = payload.title.casefold()
    media_type = payload.media_type.casefold().split(";", 1)[0].strip()

    if media_type in {"text/html", "application/xhtml+xml"}:
        sections = (ExtractedSection(_html_location(payload.kind), _extract_html(payload.body)),)
    elif payload.kind == SourceKind.PDF or media_type == "application/pdf" or title.endswith(".pdf"):
        sections = _extract_pdf(payload.body)
    elif title.endswith(".pptx") or "presentationml" in media_type:
        sections = _extract_pptx(payload.body)
    elif title.endswith(".docx") or "wordprocessingml" in media_type:
        sections = _extract_docx(payload.body)
    elif media_type.startswith("text/") or title.endswith((".txt", ".md", ".csv")):
        sections = (ExtractedSection("Document", _decode_text(payload.body)),)
    elif title.endswith(".ppt"):
        raise ContentExtractionError("Legacy .ppt files must be converted to .pptx or PDF")
    else:
        raise ContentExtractionError(
            f"Unsupported content type: {payload.media_type or 'unknown'}"
        )

    sections = tuple(section for section in sections if section.text.strip())
    if not sections:
        raise ContentExtractionError(
            "No extractable text was found; this file may require OCR"
        )
    return ExtractedContent(payload, sections)


def _extract_html(body: bytes) -> str:
    parser = TextHTMLParser()
    parser.feed(_decode_text(body))
    parser.close()
    return _normalize_text("".join(parser.parts))


def _extract_pdf(body: bytes) -> Tuple[ExtractedSection, ...]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ContentExtractionError("PDF support is missing from this add-on build") from error

    try:
        reader = PdfReader(BytesIO(body))
        return tuple(
            ExtractedSection(f"Page {index}", _normalize_text(page.extract_text() or ""))
            for index, page in enumerate(reader.pages, start=1)
        )
    except Exception as error:
        raise ContentExtractionError(f"Could not read PDF: {error}") from error


def _extract_pptx(body: bytes) -> Tuple[ExtractedSection, ...]:
    with _safe_zip(body) as archive:
        slide_names = _numbered_entries(archive, "ppt/slides/slide", ".xml")
        sections = []
        for number, name in slide_names:
            root = ElementTree.fromstring(archive.read(name))
            text = _normalize_text("\n".join(_xml_text(root, "}t")))
            sections.append(ExtractedSection(f"Slide {number}", text))
        return tuple(sections)


def _extract_docx(body: bytes) -> Tuple[ExtractedSection, ...]:
    with _safe_zip(body) as archive:
        try:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        except KeyError as error:
            raise ContentExtractionError("DOCX is missing word/document.xml") from error
        paragraphs = []
        for paragraph in root.iter():
            if not paragraph.tag.endswith("}p"):
                continue
            text = " ".join(_xml_text(paragraph, "}t"))
            if text.strip():
                paragraphs.append(text)
        return (ExtractedSection("Document", _normalize_text("\n".join(paragraphs))),)


def _safe_zip(body: bytes) -> ZipFile:
    try:
        archive = ZipFile(BytesIO(body))
    except BadZipFile as error:
        raise ContentExtractionError("Office document is not a valid ZIP archive") from error
    if sum(entry.file_size for entry in archive.infolist()) > MAX_EXPANDED_ARCHIVE_BYTES:
        archive.close()
        raise ContentExtractionError("Office document expands beyond the 200 MB limit")
    return archive


def _numbered_entries(
    archive: ZipFile, prefix: str, suffix: str
) -> Tuple[Tuple[int, str], ...]:
    entries = []
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+){re.escape(suffix)}$")
    for name in archive.namelist():
        match = pattern.match(PurePosixPath(name).as_posix())
        if match:
            entries.append((int(match.group(1)), name))
    return tuple(sorted(entries))


def _xml_text(root: ElementTree.Element, suffix: str) -> Iterable[str]:
    for element in root.iter():
        if element.tag.endswith(suffix) and element.text:
            yield element.text


def _decode_text(body: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ContentExtractionError("Text encoding could not be detected")


def _normalize_text(value: str) -> str:
    lines = []
    for line in value.replace("\r", "\n").split("\n"):
        normalized = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if normalized and (not lines or lines[-1] != normalized):
            lines.append(normalized)
    return "\n".join(lines)


def _html_location(kind: SourceKind) -> str:
    return {
        SourceKind.ASSIGNMENT: "Assignment",
        SourceKind.SYLLABUS: "Syllabus",
        SourceKind.PAGE: "Page",
    }.get(kind, "Canvas content")
