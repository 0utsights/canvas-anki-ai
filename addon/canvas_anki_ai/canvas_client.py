import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import CanvasCourse, CanvasItemKind, CanvasModule, CanvasModuleItem


DEFAULT_TIMEOUT_SECONDS = 30
LINK_PATTERN = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')


class CanvasApiError(RuntimeError):
    pass


class SameOriginRedirectHandler(HTTPRedirectHandler):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        parts = urlsplit(base_url)
        self.origin = (parts.scheme, parts.netloc)

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Mapping[str, str],
        new_url: str,
    ) -> Optional[Request]:
        destination = urlsplit(new_url)
        if (destination.scheme, destination.netloc) != self.origin:
            raise CanvasApiError("Canvas attempted to redirect to another server")
        return super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )


def normalize_canvas_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Enter a complete Canvas URL, such as https://school.instructure.com")
    if parts.query or parts.fragment:
        raise ValueError("Canvas URL cannot contain a query string or fragment")
    if parts.scheme == "http" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Canvas URL must use HTTPS")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


class CanvasClient:
    def __init__(
        self,
        base_url: str,
        access_token: str,
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.base_url = normalize_canvas_url(base_url)
        self.access_token = access_token.strip()
        self._opener = opener or build_opener(
            SameOriginRedirectHandler(self.base_url)
        ).open
        if not self.access_token:
            raise ValueError("Canvas access token is required")

    def list_active_courses(self) -> Tuple[CanvasCourse, ...]:
        query = urlencode(
            [
                ("enrollment_state", "active"),
                ("state[]", "available"),
                ("per_page", "100"),
            ]
        )
        url = f"{self.base_url}/api/v1/courses?{query}"
        courses = [self._parse_course(item) for item in self._get_paginated(url)]
        return tuple(sorted(courses, key=lambda course: course.name.casefold()))

    def list_course_modules(self, course_id: int) -> Tuple[CanvasModule, ...]:
        query = urlencode(
            [
                ("include[]", "items"),
                ("include[]", "content_details"),
                ("per_page", "100"),
            ]
        )
        url = f"{self.base_url}/api/v1/courses/{course_id}/modules?{query}"
        return tuple(
            self._parse_module(course_id, item) for item in self._get_paginated(url)
        )

    def _get_paginated(self, url: str) -> Tuple[Any, ...]:
        results: List[Any] = []
        next_url: Optional[str] = url
        while next_url:
            payload, headers = self._get_json(next_url)
            if not isinstance(payload, list):
                raise CanvasApiError("Canvas returned an unexpected paginated response")
            results.extend(payload)
            next_url = self._next_page(headers)
        return tuple(results)

    def _get_json(self, url: str) -> Tuple[Any, Mapping[str, str]]:
        self._require_same_origin(url)
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
                "User-Agent": "Canvas-Anki-AI/0.3.0",
            },
        )
        try:
            with self._opener(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
                return json.loads(body), dict(response.headers.items())
        except HTTPError as error:
            detail = self._http_error_detail(error)
            raise CanvasApiError(f"Canvas request failed ({error.code}): {detail}") from error
        except URLError as error:
            raise CanvasApiError(f"Could not connect to Canvas: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise CanvasApiError("Canvas returned invalid JSON") from error

    def _next_page(self, headers: Mapping[str, str]) -> Optional[str]:
        link_header = next(
            (value for key, value in headers.items() if key.casefold() == "link"),
            "",
        )
        links: Dict[str, str] = {
            relation: urljoin(self.base_url, url)
            for url, relation in LINK_PATTERN.findall(link_header)
        }
        next_url = links.get("next")
        if next_url:
            self._require_same_origin(next_url)
        return next_url

    def _parse_module(self, course_id: int, item: Any) -> CanvasModule:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            raise CanvasApiError("Canvas returned an invalid module record")
        module_id = item["id"]
        module_name = str(item.get("name") or f"Module {module_id}")
        module_position = self._integer(item.get("position"), 0)
        module_state = str(item.get("state") or "unknown")
        module_unlock_at = self._datetime(item.get("unlock_at"))

        raw_items = item.get("items")
        if raw_items is None:
            query = urlencode([("include[]", "content_details"), ("per_page", "100")])
            url = (
                f"{self.base_url}/api/v1/courses/{course_id}/modules/"
                f"{module_id}/items?{query}"
            )
            raw_items = self._get_paginated(url)
        if not isinstance(raw_items, (list, tuple)):
            raise CanvasApiError("Canvas returned invalid module items")

        items = tuple(
            self._parse_module_item(
                course_id,
                module_id,
                module_name,
                module_position,
                module_state,
                module_unlock_at,
                raw_item,
            )
            for raw_item in raw_items
        )
        return CanvasModule(
            course_id,
            module_id,
            module_name,
            module_position,
            module_state,
            module_unlock_at,
            items,
        )

    def _parse_module_item(
        self,
        course_id: int,
        module_id: int,
        module_name: str,
        module_position: int,
        module_state: str,
        module_unlock_at: Optional[datetime],
        item: Any,
    ) -> CanvasModuleItem:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            raise CanvasApiError("Canvas returned an invalid module item")
        details = item.get("content_details") or {}
        if not isinstance(details, dict):
            details = {}
        content_id = item.get("content_id")
        if not isinstance(content_id, int):
            content_id = None
        return CanvasModuleItem(
            course_id=course_id,
            module_id=module_id,
            item_id=item["id"],
            content_id=content_id,
            title=str(item.get("title") or f"Item {item['id']}"),
            kind=CanvasItemKind.from_canvas(item.get("type")),
            position=self._integer(item.get("position"), 0),
            module_name=module_name,
            module_position=module_position,
            module_state=module_state,
            html_url=self._optional_string(item.get("html_url")),
            due_at=self._datetime(details.get("due_at")),
            unlock_at=self._datetime(details.get("unlock_at")),
            lock_at=self._datetime(details.get("lock_at")),
            module_unlock_at=module_unlock_at,
            published=item.get("published") is not False,
        )

    def _require_same_origin(self, url: str) -> None:
        expected = urlsplit(self.base_url)
        actual = urlsplit(url)
        if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
            raise CanvasApiError("Canvas pagination attempted to leave the configured server")

    @staticmethod
    def _parse_course(item: Any) -> CanvasCourse:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            raise CanvasApiError("Canvas returned an invalid course record")
        name = item.get("name") or item.get("course_code") or f"Course {item['id']}"
        course_code = item.get("course_code") or name
        return CanvasCourse(item["id"], str(name), str(course_code))

    @staticmethod
    def _datetime(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _integer(value: Any, default: int) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) else default

    @staticmethod
    def _optional_string(value: Any) -> Optional[str]:
        return str(value) if value else None

    @staticmethod
    def _http_error_detail(error: HTTPError) -> str:
        try:
            payload = json.loads(error.read().decode("utf-8"))
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("error")
                if message:
                    return str(message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return error.reason or "Unknown error"
