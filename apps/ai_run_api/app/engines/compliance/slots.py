"""Compliance domain slot definitions and filename-based matching."""

from __future__ import annotations

import os
import re
from typing import NamedTuple


EXT_DOCS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
EXT_DATA = {".xlsx", ".xls", ".csv"}
EXT_ALL = EXT_DOCS | EXT_DATA


def _rx(expr: str) -> re.Pattern[str]:
    return re.compile(expr, re.IGNORECASE)


class SlotDef(NamedTuple):
    name: str
    display_name: str
    required: bool
    patterns: list[re.Pattern[str]]
    accepted_exts: set[str]


SLOTS: list[SlotDef] = [
    SlotDef(
        name="compliance.contract.sample",
        display_name="\ud45c\uc900 \uadfc\ub85c/\ud558\ub3c4\uae09 \uacc4\uc57d\uc11c",
        required=True,
        patterns=[
            _rx(r"(\uadfc\ub85c|\ud558\ub3c4\uae09).*\uacc4\uc57d"),
            _rx(r"contract.*sample"),
        ],
        accepted_exts=EXT_ALL,
    ),
    SlotDef(
        name="compliance.education.privacy",
        display_name="\uac1c\uc778\uc815\ubcf4\ubcf4\ud638 \uad50\uc721 \uc774\uc218 \ud604\ud669",
        required=True,
        patterns=[
            _rx(r"\uac1c\uc778\uc815\ubcf4.*(\uad50\uc721|\uc774\uc218)"),
            _rx(r"privacy.*(edu|education)"),
        ],
        accepted_exts=EXT_ALL,
    ),
    SlotDef(
        name="compliance.fair.trade",
        display_name="\uacf5\uc815\uac70\ub798 \uc790\uc728 \uc810\uac80\ud45c",
        required=True,
        patterns=[
            _rx(r"\uacf5\uc815\uac70\ub798.*(\uc810\uac80|\uc790\uc728)"),
            _rx(r"fair.*trade.*(check|inspect)"),
        ],
        accepted_exts=EXT_ALL,
    ),
    SlotDef(
        name="compliance.ethics.report",
        display_name="\uc724\ub9ac\uacbd\uc601 \uc2e0\uace0 \ud604\ud669",
        required=False,
        patterns=[
            _rx(r"(\ubd80\uc815\ubd80\ud328|\uc724\ub9ac\uacbd\uc601)"),
            _rx(r"ethics.*(report|status)"),
        ],
        accepted_exts=EXT_ALL,
    ),
    SlotDef(
        name="compliance.education.plan",
        display_name="\ubc95\uc815\uc758\ubb34 \uad50\uc721 \uacc4\ud68d\uc11c",
        required=False,
        patterns=[
            _rx(r"(\ucef4\ud50c\ub77c\uc774\uc5b8\uc2a4|\ubc95\uc815\uc758\ubb34).*\uad50\uc721"),
            _rx(r"compliance.*(plan|edu|education)"),
        ],
        accepted_exts=EXT_ALL,
    ),
    SlotDef(
        name="compliance.education.attendance",
        display_name="\uad50\uc721 \ucd9c\uc11d\ubd80",
        required=False,
        patterns=[
            _rx(r"\ucd9c\uc11d\ubd80|\ucd9c\uc11d\uba85\ub2e8"),
            _rx(r"\uad50\uc721.*\ucd9c\uc11d"),
            _rx(r"attend"),
        ],
        accepted_exts=EXT_DOCS,
    ),
    SlotDef(
        name="compliance.education.photo",
        display_name="\uad50\uc721\uc77c \uc0ac\uc9c4",
        required=False,
        patterns=[
            _rx(r"\uad50\uc721.*\uc0ac\uc9c4"),
            _rx(r"\uad50\uc721\uc77c\s*\uc0ac\uc9c4"),
            _rx(r"\uad50\uc721\ud604\uc7a5"),
            _rx(r"edu.*photo"),
        ],
        accepted_exts=EXT_DOCS,
    ),
]


def get_required_slot_names() -> list[str]:
    return [s.name for s in SLOTS if s.required]


def get_all_slot_names() -> list[str]:
    return [s.name for s in SLOTS]


def match_filename_to_slot(filename: str) -> tuple[str, float] | None:
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    clean_name = filename.replace("_", " ").replace("-", " ")
    clean_name = re.sub(r"\s+", " ", clean_name).strip().lower()

    for slot in SLOTS:
        if ext not in slot.accepted_exts:
            continue
        for pat in slot.patterns:
            if pat.search(clean_name):
                return slot.name, 1.0
    return None
