"""Safety domain slot definitions and filename-based matching."""

from __future__ import annotations

import re
from typing import NamedTuple


def _rx(expr: str) -> re.Pattern[str]:
    return re.compile(expr, re.IGNORECASE)


class SlotDef(NamedTuple):
    name: str
    display_name: str
    required: bool
    patterns: list[re.Pattern[str]]


SLOTS: list[SlotDef] = [
    SlotDef(
        name="safety.education.status",
        display_name="\uc548\uc804\uad50\uc721 \uc774\uc218 \ud604\ud669",
        required=True,
        patterns=[
            _rx(r"\uc548\uc804\uad50\uc721.*(\ud604\ud669|\uc774\uc218)"),
            _rx(r"\uad50\uc721.*(\ud604\ud669|\uc774\uc218)"),
            _rx(r"edu.*status"),
        ],
    ),
    SlotDef(
        name="safety.fire.inspection",
        display_name="\uc18c\ubc29 \uc810\uac80 \uacb0\uacfc",
        required=True,
        patterns=[
            _rx(r"\uc18c\ubc29.*(\uc810\uac80|\uc790\uccb4)"),
            _rx(r"fire.*(inspection|check|insp)"),
        ],
    ),
    SlotDef(
        name="safety.risk.assessment",
        display_name="\uc704\ud5d8\uc131 \ud3c9\uac00",
        required=True,
        patterns=[
            _rx(r"\uc704\ud5d8\uc131?\s*\ud3c9\uac00"),
            _rx(r"risk.?assess"),
        ],
    ),
    SlotDef(
        name="safety.management.system",
        display_name="\uc548\uc804\ubcf4\uac74 \uad00\ub9ac\uccb4\uacc4",
        required=True,
        patterns=[
            _rx(r"\uc548\uc804\ubcf4\uac74\uad00\ub9ac\uccb4\uacc4"),
            _rx(r"\uad00\ub9ac\uccb4\uacc4.*\ub9e4\ub274\uc5bc"),
            _rx(r"management.*system"),
        ],
    ),
    SlotDef(
        name="safety.site.photos",
        display_name="\ud604\uc7a5 \uc0ac\uc9c4",
        required=False,
        patterns=[
            _rx(r"\ud604\uc7a5.*\uc0ac\uc9c4"),
            _rx(r"site.?photo"),
        ],
    ),
    SlotDef(
        name="safety.education.attendance",
        display_name="\uad50\uc721 \ucd9c\uc11d\ubd80",
        required=False,
        patterns=[
            _rx(r"\ucd9c\uc11d\ubd80|\ucd9c\uc11d\uba85\ub2e8"),
            _rx(r"\uad50\uc721.*\ucd9c\uc11d"),
            _rx(r"attend"),
        ],
    ),
    SlotDef(
        name="safety.education.photo",
        display_name="\uad50\uc721\uc77c \uc0ac\uc9c4",
        required=False,
        patterns=[
            _rx(r"\uad50\uc721.*\uc0ac\uc9c4"),
            _rx(r"\uad50\uc721\uc77c\s*\uc0ac\uc9c4"),
            _rx(r"edu.*photo"),
        ],
    ),
    SlotDef(
        name="safety.tbm",
        display_name="TBM(\uc791\uc5c5 \uc804 \ud68c\uc758)",
        required=False,
        patterns=[
            _rx(r"\btbm\b"),
            _rx(r"tool.?box.?meet"),
            _rx(r"\uc791\uc5c5\uc804.*\ud68c\uc758"),
        ],
    ),
]


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    clean_name = filename.replace("_", " ").replace("-", " ")
    clean_name = re.sub(r"\s+", " ", clean_name).strip().lower()
    for slot in SLOTS:
        for pat in slot.patterns:
            if pat.search(clean_name):
                confidence = 0.9 if slot.required else 0.85
                return slot.name, confidence
    return None
