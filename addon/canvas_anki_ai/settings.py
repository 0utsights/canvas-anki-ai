from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple


@dataclass(frozen=True)
class AddonSettings:
    canvas_base_url: str = ""
    selected_course_ids: Tuple[int, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AddonSettings":
        raw_ids = value.get("selected_course_ids", [])
        selected_ids = tuple(
            sorted(
                {
                    course_id
                    for course_id in raw_ids
                    if isinstance(course_id, int) and not isinstance(course_id, bool)
                }
            )
        )
        return cls(
            canvas_base_url=str(value.get("canvas_base_url", "")),
            selected_course_ids=selected_ids,
        )

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "canvas_base_url": self.canvas_base_url,
            "selected_course_ids": list(self.selected_course_ids),
        }
