from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .models import CanvasItemKind, CanvasModule, CanvasModuleItem
from .relevance import ContentCategory, classify_text


@dataclass(frozen=True)
class RankedMaterial:
    item: CanvasModuleItem
    score: int
    reasons: Tuple[str, ...]


KIND_SCORES: Dict[CanvasItemKind, int] = {
    CanvasItemKind.ASSIGNMENT: 35,
    CanvasItemKind.QUIZ: 32,
    CanvasItemKind.FILE: 28,
    CanvasItemKind.PAGE: 26,
    CanvasItemKind.DISCUSSION: 18,
    CanvasItemKind.EXTERNAL_TOOL: 12,
    CanvasItemKind.EXTERNAL_URL: 10,
    CanvasItemKind.OTHER: 0,
}

STATE_SCORES = {
    "started": 24,
    "unlocked": 18,
    "completed": -8,
    "locked": -35,
}


def rank_current_material(
    modules: Iterable[CanvasModule],
    now: Optional[datetime] = None,
) -> Tuple[RankedMaterial, ...]:
    current_time = _as_utc(now or datetime.now(timezone.utc))
    module_list = tuple(modules)
    current_module_position = _current_module_position(module_list, current_time)

    ranked = [
        _rank_item(item, current_time, current_module_position)
        for module in module_list
        for item in module.items
        if item.published
    ]
    return tuple(
        sorted(
            ranked,
            key=lambda material: (
                -material.score,
                material.item.module_position,
                material.item.position,
                material.item.title.casefold(),
            ),
        )
    )


def _rank_item(
    item: CanvasModuleItem,
    now: datetime,
    current_module_position: int,
) -> RankedMaterial:
    score = KIND_SCORES[item.kind]
    reasons: List[str] = [f"{item.kind.value} source"]

    state_score = STATE_SCORES.get(item.module_state, 0)
    if state_score:
        score += state_score
        reasons.append(f"module is {item.module_state}")

    if current_module_position and item.module_state != "locked":
        distance = abs(current_module_position - item.module_position)
        position_score = max(0, 18 - distance * 5)
        if position_score:
            score += position_score
            reasons.append("near the current module anchor")

    score += _date_score(item.module_unlock_at, now, reasons, "module opened")
    score += _date_score(item.unlock_at, now, reasons, "item opened")
    score += _due_score(item.due_at, now, reasons)

    if item.lock_at and _as_utc(item.lock_at) < now:
        score -= 25
        reasons.append("availability window ended")

    if classify_text(item.title).category == ContentCategory.LOGISTICS:
        score -= 45
        reasons.append("title appears logistical")

    return RankedMaterial(item, score, tuple(reasons))


def _current_module_position(modules: Tuple[CanvasModule, ...], now: datetime) -> int:
    started = [module.position for module in modules if module.state == "started"]
    if started:
        return max(started)

    assessment_positions = [
        module.position
        for module in modules
        if any(
            item.due_at
            and -14
            <= (_as_utc(item.due_at) - now).total_seconds() / 86400
            <= 21
            for item in module.items
        )
    ]
    if assessment_positions:
        return max(assessment_positions)

    recently_opened = [
        module.position
        for module in modules
        if module.unlock_at
        and 0 <= (now - _as_utc(module.unlock_at)).total_seconds() / 86400 <= 35
    ]
    if recently_opened:
        return max(recently_opened)

    completed = [module.position for module in modules if module.state == "completed"]
    if completed:
        last_completed = max(completed)
        next_positions = [
            module.position
            for module in modules
            if module.position > last_completed and module.state != "locked"
        ]
        return min(next_positions, default=last_completed)

    return 0


def _date_score(
    value: Optional[datetime],
    now: datetime,
    reasons: List[str],
    label: str,
) -> int:
    if value is None:
        return 0
    elapsed_days = (now - _as_utc(value)).total_seconds() / 86400
    if 0 <= elapsed_days <= 21:
        reasons.append(f"{label} recently")
        return 20
    if -7 <= elapsed_days < 0:
        reasons.append(f"{label} soon")
        return 8
    if elapsed_days > 90:
        return -10
    return 0


def _due_score(
    value: Optional[datetime], now: datetime, reasons: List[str]
) -> int:
    if value is None:
        return 0
    days_until = (_as_utc(value) - now).total_seconds() / 86400
    if -7 <= days_until <= 14:
        reasons.append("assessment is near the current date")
        return max(15, 36 - int(abs(days_until) * 2))
    if days_until < -30:
        return -12
    if days_until > 45:
        return -5
    return 0


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
