import sys
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.content_extractor import extract_content
from canvas_anki_ai.models import ContentPayload, SourceKind


def payload(title: str, media_type: str, body: bytes, kind=SourceKind.OTHER):
    return ContentPayload(1, "source", title, kind, media_type, body, "https://example.edu")


def zipped(entries) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    return output.getvalue()


def simple_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii") + value + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(output)


class ExtractContentTests(unittest.TestCase):
    def test_extracts_readable_html_without_scripts(self) -> None:
        content = extract_content(
            payload(
                "Lesson",
                "text/html",
                b"<h1>Cell Cycle</h1><p>DNA is replicated.</p><script>ignore()</script>",
                SourceKind.PAGE,
            )
        )

        self.assertEqual(content.sections[0].location, "Page")
        self.assertEqual(content.sections[0].text, "Cell Cycle\nDNA is replicated.")

    def test_extracts_powerpoint_by_slide(self) -> None:
        body = zipped(
            {
                "ppt/slides/slide2.xml": '<p:sld xmlns:p="p" xmlns:a="a"><a:t>Second</a:t></p:sld>',
                "ppt/slides/slide1.xml": '<p:sld xmlns:p="p" xmlns:a="a"><a:t>First</a:t><a:t>Concept</a:t></p:sld>',
            }
        )

        content = extract_content(
            payload("lecture.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", body)
        )

        self.assertEqual([section.location for section in content.sections], ["Slide 1", "Slide 2"])
        self.assertEqual(content.sections[0].text, "First\nConcept")

    def test_extracts_word_document(self) -> None:
        body = zipped(
            {
                "word/document.xml": '<w:document xmlns:w="w"><w:body><w:p><w:r><w:t>First paragraph</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:body></w:document>'
            }
        )

        content = extract_content(
            payload("reading.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", body)
        )

        self.assertEqual(content.sections[0].text, "First paragraph\nSecond paragraph")

    def test_extracts_pdf_by_page(self) -> None:
        content = extract_content(
            payload("reading.pdf", "application/pdf", simple_pdf("Hello PDF"), SourceKind.PDF)
        )

        self.assertEqual(content.sections[0].location, "Page 1")
        self.assertIn("Hello PDF", content.sections[0].text)


if __name__ == "__main__":
    unittest.main()
