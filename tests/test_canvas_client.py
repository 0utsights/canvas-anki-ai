import json
import sys
import unittest
from pathlib import Path
from urllib.request import Request


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.canvas_client import (
    CanvasApiError,
    CanvasClient,
    SameOriginRedirectHandler,
    normalize_canvas_url,
)


class FakeResponse:
    def __init__(self, payload, headers=None) -> None:
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self, size=None) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return self.responses.pop(0)


class BinaryResponse(FakeResponse):
    def read(self, size=None) -> bytes:
        return self.payload if size is None else self.payload[:size]


class NormalizeCanvasUrlTests(unittest.TestCase):
    def test_normalizes_secure_url(self) -> None:
        self.assertEqual(
            normalize_canvas_url(" https://school.instructure.com/ "),
            "https://school.instructure.com",
        )

    def test_rejects_insecure_remote_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            normalize_canvas_url("http://school.example.edu")


class CanvasClientTests(unittest.TestCase):
    def test_lists_and_sorts_paginated_active_courses(self) -> None:
        opener = FakeOpener(
            [
                FakeResponse(
                    [{"id": 2, "name": "Zoology", "course_code": "BIO 202"}],
                    {
                        "Link": '<https://school.instructure.com/api/v1/courses?page=2>; rel="next"'
                    },
                ),
                FakeResponse(
                    [{"id": 1, "name": "Algebra", "course_code": "MATH 101"}]
                ),
            ]
        )
        client = CanvasClient("https://school.instructure.com", "secret", opener)

        courses = client.list_active_courses()

        self.assertEqual([course.name for course in courses], ["Algebra", "Zoology"])
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(
            opener.requests[0][0].get_header("Authorization"), "Bearer secret"
        )

    def test_rejects_cross_origin_pagination(self) -> None:
        opener = FakeOpener(
            [
                FakeResponse(
                    [],
                    {"Link": '<https://attacker.example/courses?page=2>; rel="next"'},
                )
            ]
        )
        client = CanvasClient("https://school.instructure.com", "secret", opener)

        with self.assertRaisesRegex(CanvasApiError, "leave the configured server"):
            client.list_active_courses()

    def test_requires_access_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "token"):
            CanvasClient("https://school.instructure.com", "")

    def test_rejects_cross_origin_redirect(self) -> None:
        handler = SameOriginRedirectHandler("https://school.instructure.com")

        with self.assertRaisesRegex(CanvasApiError, "redirect to another server"):
            handler.redirect_request(
                Request("https://school.instructure.com/api/v1/courses"),
                None,
                302,
                "Found",
                {},
                "https://attacker.example/collect",
            )

    def test_discovers_inline_and_separately_loaded_module_items(self) -> None:
        opener = FakeOpener(
            [
                FakeResponse(
                    [
                        {
                            "id": 10,
                            "name": "Current Unit",
                            "position": 3,
                            "state": "started",
                            "unlock_at": "2026-08-20T12:00:00Z",
                            "items": [
                                {
                                    "id": 100,
                                    "content_id": 500,
                                    "title": "Problem Set 3",
                                    "type": "Assignment",
                                    "position": 2,
                                    "published": True,
                                    "content_details": {
                                        "due_at": "2026-08-28T23:59:00Z"
                                    },
                                }
                            ],
                        },
                        {
                            "id": 11,
                            "name": "Reference Material",
                            "position": 4,
                            "state": "unlocked",
                        },
                    ]
                ),
                FakeResponse(
                    [
                        {
                            "id": 101,
                            "content_id": 501,
                            "title": "Lecture Slides",
                            "type": "File",
                            "position": 1,
                            "published": True,
                        }
                    ]
                ),
            ]
        )
        client = CanvasClient("https://school.instructure.com", "secret", opener)

        modules = client.list_course_modules(7)

        self.assertEqual(len(modules), 2)
        self.assertEqual(modules[0].items[0].title, "Problem Set 3")
        self.assertEqual(modules[0].items[0].due_at.year, 2026)
        self.assertEqual(modules[1].items[0].title, "Lecture Slides")
        self.assertIn("/courses/7/modules/11/items?", opener.requests[1][0].full_url)

    def test_fetches_page_and_file_without_sending_token_to_download_host(self) -> None:
        api_opener = FakeOpener(
            [
                FakeResponse(
                    {
                        "title": "Cell Cycle",
                        "body": "<p>DNA replication occurs during S phase.</p>",
                        "html_url": "https://school.instructure.com/courses/7/pages/cell-cycle",
                    }
                ),
                FakeResponse(
                    {
                        "display_name": "lecture.pdf",
                        "content-type": "application/pdf",
                        "size": 7,
                        "url": "https://cdn.example.edu/signed-file",
                        "html_url": "https://school.instructure.com/files/500",
                    }
                ),
            ]
        )
        download_opener = FakeOpener(
            [BinaryResponse(b"PDFDATA", {"Content-Type": "application/pdf"})]
        )
        client = CanvasClient(
            "https://school.instructure.com",
            "secret",
            api_opener,
            download_opener,
        )
        page = self._module_item(100, "Page", "https://school.instructure.com/api/page")
        file_item = self._module_item(
            101, "File", "https://school.instructure.com/api/file"
        )

        page_payload = client.fetch_item_content(page)
        file_payload = client.fetch_item_content(file_item)

        self.assertIn(b"DNA replication", page_payload.body)
        self.assertEqual(file_payload.title, "lecture.pdf")
        self.assertIsNone(
            download_opener.requests[0][0].get_header("Authorization")
        )

    def test_fetches_syllabus_html(self) -> None:
        opener = FakeOpener(
            [
                FakeResponse(
                    {
                        "id": 7,
                        "name": "Biology",
                        "syllabus_body": "<h2>Learning outcomes</h2>",
                        "html_url": "https://school.instructure.com/courses/7",
                    }
                )
            ]
        )
        client = CanvasClient("https://school.instructure.com", "secret", opener)

        syllabus = client.fetch_course_syllabus(7)

        self.assertEqual(syllabus.title, "Biology Syllabus")
        self.assertIn(b"Learning outcomes", syllabus.body)

    @staticmethod
    def _module_item(item_id, item_type, api_url):
        from canvas_anki_ai.models import CanvasItemKind, CanvasModuleItem

        return CanvasModuleItem(
            course_id=7,
            module_id=10,
            item_id=item_id,
            content_id=500,
            title=f"Item {item_id}",
            kind=CanvasItemKind.from_canvas(item_type),
            position=1,
            module_name="Week One",
            module_position=1,
            module_state="started",
            api_url=api_url,
        )


if __name__ == "__main__":
    unittest.main()
