# app/engines/safety/cross_validators.py

"""Safety domain cross validators."""

from __future__ import annotations

import re
from typing import Any

# (attendance slot, photo slot)
CROSS_PAIRS: list[tuple[str, str]] = [
    ("safety.education.attendance", "safety.education.photo"),
]


def _count_attendance_names(extracted: dict) -> int | None:
    """Estimate attendance headcount from OCR/PDF text."""
    text = (extracted.get("text") or "").strip()
    if not text:
        return None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Heuristic 1: numbered row parsing (most stable for attendance tables).
    row_nums: set[int] = set()
    for line in lines:
        m = re.match(r"^\s*(\d{1,3})(?:[\s.)-]+|$)", line)
        if not m:
            continue
        num = int(m.group(1))
        if 1 <= num <= 500:
            row_nums.add(num)
    if row_nums:
        max_num = max(row_nums)
        if min(row_nums) == 1 and len(row_nums) >= max(3, int(max_num * 0.6)):
            return max_num
        return len(row_nums)

    # Heuristic 2: count lines with two or more names (name + sign columns).
    count = 0
    for line in lines:
        names = re.findall(r"[가-힣]{2,4}", line)
        if len(names) >= 2:
            count += 1
    if count > 0:
        return count

    # Heuristic 3: explicit total like "12명"
    m = re.search(r"(\d+)\s*명", text)
    if m:
        return int(m.group(1))

    return None


def _count_photo_people(extracted: dict) -> int | None:
    """Extract people count from photo-analysis extras."""
    # Attendance images can be mapped as "photo" slot.
    # When OCR text contains numbered rows, prefer table count over YOLO.
    text_count = _count_attendance_names(extracted)
    if text_count is not None and text_count >= 3:
        return text_count

    extras = extracted.get("extras", {}) or {}

    counts: list[int] = []
    for key in ("person_count", "person_count_yolo", "person_count_llm"):
        value = extras.get(key)
        if value is None:
            continue
        try:
            counts.append(int(value))
        except (TypeError, ValueError):
            m = re.search(r"\d+", str(value))
            if m:
                counts.append(int(m.group(0)))
    if counts:
        # Choose the largest available estimate to avoid under-counting.
        return max(counts)

    obj_str = str(extras.get("detected_objects", ""))
    if obj_str:
        person_mentions = re.findall(r"(?i)(person|people|사람|인원)", obj_str)
        if person_mentions:
            return len(person_mentions)

    scene = str(extras.get("scene_description", ""))
    m = re.search(r"(\d+)\s*(?:명|people|persons)", scene, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return None


def cross_validate_slot(extractions_by_slot: dict[str, list[dict]]) -> list[dict[str, Any]]:
    """Compare attendance vs photo headcount."""
    out: list[dict[str, Any]] = []

    for slot_a, slot_b in CROSS_PAIRS:
        exs_a = extractions_by_slot.get(slot_a) or []
        exs_b = extractions_by_slot.get(slot_b) or []
        if not exs_a or not exs_b:
            continue

        ext_a = exs_a[0]
        ext_b = exs_b[0]

        attendance_count = _count_attendance_names(ext_a)
        photo_count = _count_photo_people(ext_b)

        reasons: list[str] = []
        extras: dict[str, Any] = {}

        if attendance_count is None:
            reasons.append("CROSS_ATTENDANCE_PARSE_FAILED")
            extras["detail"] = "출석부에서 인원수를 추출하지 못했습니다."
        elif photo_count is None:
            reasons.append("CROSS_PHOTO_COUNT_FAILED")
            photo_extras = ext_b.get("extras", {}) or {}
            yolo_status = str(photo_extras.get("yolo_status", "UNKNOWN"))
            vision_status = str(photo_extras.get("vision_status", "UNKNOWN"))
            extras["detail"] = (
                "교육사진에서 인원수를 감지하지 못했습니다. "
                f"(YOLO={yolo_status}, Vision={vision_status})"
            )
        else:
            extras["attendance_count"] = str(attendance_count)
            extras["photo_count"] = str(photo_count)
            diff = abs(attendance_count - photo_count)

            tolerance = 2 if attendance_count <= 10 else max(2, int(attendance_count * 0.2))
            if diff > tolerance:
                reasons.append("CROSS_HEADCOUNT_MISMATCH")
                extras["diff"] = str(diff)
                extras["tolerance"] = str(tolerance)
                extras["detail"] = (
                    f"출석부 {attendance_count}명 vs 사진 {photo_count}명 "
                    f"(차이 {diff}명, 허용 {tolerance}명)"
                )

        verdict = "NEED_CLARIFY" if reasons else "PASS"
        out.append(
            {
                "slot_name": f"{slot_a}__x__{slot_b}",
                "reasons": reasons,
                "verdict": verdict,
                "extras": extras,
            }
        )

    return out
