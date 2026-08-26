import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))

from canvas_anki_ai.material_ranking import rank_current_material
from canvas_anki_ai.models import CanvasItemKind, CanvasModule, CanvasModuleItem


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def make_item(
    item_id: int,
    title: str,
    kind: CanvasItemKind,
    module_id: int,
    module_name: str,
    module_position: int,
    module_state: str,
    **dates,
) -> CanvasModuleItem:
    return CanvasModuleItem(
        course_id=1,
        module_id=module_id,
        item_id=item_id,
        content_id=item_id + 100,
        title=title,
        kind=kind,
        position=1,
        module_name=module_name,
        module_position=module_position,
        module_state=module_state,
        **dates,
    )


class RankCurrentMaterialTests(unittest.TestCase):
    def test_prioritizes_nearby_assignment_and_current_module(self) -> None:
        old_file = make_item(
            1,
            "Week One Slides",
            CanvasItemKind.FILE,
            10,
            "Week One",
            1,
            "completed",
            module_unlock_at=NOW - timedelta(days=120),
        )
        current_assignment = make_item(
            2,
            "Cell Division Problems",
            CanvasItemKind.ASSIGNMENT,
            20,
            "Week Eight",
            8,
            "started",
            module_unlock_at=NOW - timedelta(days=3),
            due_at=NOW + timedelta(days=2),
        )
        modules = (
            CanvasModule(1, 10, "Week One", 1, "completed", None, (old_file,)),
            CanvasModule(1, 20, "Week Eight", 8, "started", None, (current_assignment,)),
        )

        ranked = rank_current_material(modules, NOW)

        self.assertEqual(ranked[0].item, current_assignment)
        self.assertIn("assessment is near the current date", ranked[0].reasons)

    def test_excludes_unpublished_items(self) -> None:
        hidden = make_item(
            3,
            "Hidden Exam",
            CanvasItemKind.QUIZ,
            30,
            "Future",
            9,
            "locked",
            published=False,
        )
        modules = (CanvasModule(1, 30, "Future", 9, "locked", None, (hidden,)),)

        self.assertEqual(rank_current_material(modules, NOW), ())

    def test_does_not_assume_last_module_is_current_when_all_are_unlocked(self) -> None:
        first = make_item(
            4,
            "Unit One Reading",
            CanvasItemKind.PAGE,
            40,
            "Unit One",
            1,
            "unlocked",
        )
        last = make_item(
            5,
            "Unit Twelve Reading",
            CanvasItemKind.PAGE,
            50,
            "Unit Twelve",
            12,
            "unlocked",
        )
        modules = (
            CanvasModule(1, 40, "Unit One", 1, "unlocked", None, (first,)),
            CanvasModule(1, 50, "Unit Twelve", 12, "unlocked", None, (last,)),
        )

        ranked = rank_current_material(modules, NOW)

        self.assertEqual(ranked[0].score, ranked[1].score)


if __name__ == "__main__":
    unittest.main()
