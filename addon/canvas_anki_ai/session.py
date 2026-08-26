from dataclasses import dataclass
from typing import Tuple

from .models import CanvasCourse


@dataclass
class SessionState:
    canvas_base_url: str = ""
    access_token: str = ""
    courses: Tuple[CanvasCourse, ...] = ()
    courses_loaded: bool = False


SESSION = SessionState()
