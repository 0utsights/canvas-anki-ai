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

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return self.responses.pop(0)


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


if __name__ == "__main__":
    unittest.main()
