"""Submit pipeline for full AI document analysis."""

from __future__ import annotations

import asyncio
import importlib
import json
import re as _re
from collections import defaultdict
from datetime import date

from app.engines.registry import get_rules_module, get_slots_module
from app.extractors.ocr.ocr_router import extract_image
from app.extractors.pdf_text import extract_pdf
from app.extractors.xlsx import extract_xlsx
from app.llm.client import ask_llm, ask_llm_vision
from app.llm.prompts import (
    CLARIFICATION_TEMPLATE,
    DATA_ANALYSIS,
    IMAGE_VISION,
    IMAGE_VISION_USER,
    JUDGE_FINAL,
    PASS_RESULT_TEMPLATE,
    PDF_ANALYSIS,
    get_prompt,
)
from app.pipeline.triage import triage_files
from app.schemas.run import Clarification, FileRef, SlotResult, SubmitRequest, SubmitResponse
from app.storage.downloader import download_file


def _safe_json(raw: str) -> dict:
    """Parse JSON from plain text or fenced markdown."""
    text = (raw or "").strip()
    m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


_DOMAIN_VALIDATORS: dict[str, object] = {}


def _get_slot_validator(domain: str):
    if domain not in _DOMAIN_VALIDATORS:
        try:
            _DOMAIN_VALIDATORS[domain] = importlib.import_module(f"app.engines.{domain}.validators")
        except ModuleNotFoundError:
            _DOMAIN_VALIDATORS[domain] = None
    return _DOMAIN_VALIDATORS[domain]


def _dedupe_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _reason_descriptions(domain: str, reasons: list[str]) -> list[str]:
    # Map reason codes to human-readable labels first, then fallback to raw code.
    manual_labels = {
        "PARSE_FAILED": "파싱 실패",
        "E3_BILL_FIELDS_MISSING": "고지서에서 기간 또는 사용량 정보를 읽지 못했습니다.",
        "E3_BILL_MISMATCH": "고지서 합계와 사용량 합계가 일치하지 않습니다.",
        "BASELINE_2024_MISSING": "2024년 기준 데이터가 없어 피크 비교를 진행할 수 없습니다.",
        "BASELINE_INVALID": "기준 연도 데이터가 유효하지 않아 피크 비교를 진행할 수 없습니다.",
        "E_PEAK_SPIKE_FAIL": "전력 피크 사용량이 기준 대비 급증했습니다.",
        "E_PEAK_SPIKE_WARN": "전력 피크 사용량이 기준 대비 상승했습니다.",
        "E_WASTE_LIST_PARSE_FAILED": "폐기물 처리 목록을 읽지 못했습니다.",
        "E_WASTE_EVIDENCE_MISSING": "폐기물 처리 증빙이 누락되었습니다.",
        "E_WASTE_EVIDENCE_FIELDS_WEAK": "폐기물 증빙의 필수 정보가 부족합니다.",
        "E_WASTE_NAME_MISMATCH": "폐기물 목록과 증빙 품목명이 일치하지 않습니다.",
        "E_INVENTORY_PARSE_FAILED": "유해물질 목록을 읽지 못했습니다.",
        "E_MSDS_MISSING_REQUIRED": "필수 MSDS 문서가 누락되었습니다.",
        "E_MSDS_MISSING_OPTIONAL": "권장 MSDS 문서 일부가 누락되었습니다.",
        "CROSS_HEADCOUNT_MISMATCH": "출석부 인원과 사진 인원이 일치하지 않습니다.",
        "CROSS_ATTENDANCE_PARSE_FAILED": "출석부 인원 추출에 실패했습니다.",
        "CROSS_PHOTO_COUNT_FAILED": "사진 인원 추출에 실패했습니다.",
    }
    try:
        reason_map = getattr(get_rules_module(domain), "REASON_CODES", {}) or {}
    except Exception:
        reason_map = {}
    return _dedupe_lines(
        [
            str(manual_labels.get(code) or reason_map.get(code, code))
            for code in reasons
            if code and code != "INFO_ANALYSIS_OK"
        ]
    )


def _slot_display_name(domain: str, slot_name: str) -> str:
    try:
        slots_mod = get_slots_module(domain)
        display_name_map = {s.name: s.display_name for s in slots_mod.SLOTS}
        return str(display_name_map.get(slot_name) or slot_name)
    except Exception:
        return slot_name


def _pick_first(data: dict, *keys: str):
    for key in keys:
        if key in data and data.get(key) is not None:
            return data.get(key)
    return None


def _to_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    m = _re.search(r"-?\d+", text)
    if not m:
        return None
    try:
        return int(m.group(0))
    except Exception:
        return None


def _status_label(status: str) -> str:
    mapping = {
        "SUCCESS": "정상",
        "FAILED": "실패",
        "UNREADABLE": "판독 불가",
        "FALLBACK_VISION": "OCR 실패(비전 대체)",
        "SKIPPED": "미실행",
    }
    return mapping.get(status, status)


def _build_success_points(domain: str, slot_name: str, file_names: list[str], extras: dict[str, str]) -> str:
    points: list[str] = []
    slot_display = _slot_display_name(domain, slot_name)
    if file_names:
        points.append(f"문서 분류: '{slot_display}' 항목으로 자동 분류했습니다.")
        points.append(f"매칭 결과: 제출 파일 {len(file_names)}건이 '{slot_display}' 기준으로 정상 확인되었습니다.")
    if extras.get("recognition_result"):
        points.append(f"판독 결과: {extras['recognition_result']}")
    if extras.get("summary"):
        points.append(f"AI 분석 요약: {extras['summary']}")
    ocr_status = str(extras.get("ocr_status", "")).upper()
    if ocr_status in {"SUCCESS", "FALLBACK_VISION"}:
        points.append(f"문서 판독(OCR): {_status_label(ocr_status)}")
    vision_status = str(extras.get("vision_status", "")).upper()
    if vision_status == "SUCCESS":
        points.append("이미지 판독(Vision): 정상")
    yolo_status = str(extras.get("yolo_status", "")).upper()
    if yolo_status == "SUCCESS":
        points.append("인원 감지(YOLO): 정상")
    if extras.get("person_count"):
        points.append(f"사진 인원 감지 결과: {extras['person_count']}명")
    if extras.get("attendance_count") and extras.get("photo_count"):
        points.append(
            f"교차 검증 결과: 출석부 {extras['attendance_count']}명 / "
            f"사진 {extras['photo_count']}명으로 허용 범위 내 일치했습니다."
        )
    if extras.get("detail"):
        points.append(str(extras["detail"]))
    if not points:
        points.append("필수 검증 항목을 확인해 종합 판정했습니다.")
    return "\n".join(f"- {p}" for p in _dedupe_lines(points))


def _build_issue_points(verdict: str, reason_desc: list[str], extras: dict[str, str]) -> str:
    points: list[str] = []
    if extras.get("recognition_result"):
        points.append(f"판독 결과: {extras['recognition_result']}")
    if verdict == "NEED_FIX":
        points.append("문서 인식/형식 오류로 자동 판정이 어려워 재제출이 필요합니다.")
    else:
        points.append("자동 판독은 완료되었지만 확인 또는 소명이 필요한 항목이 있습니다.")
    if reason_desc:
        points.append(f"주요 사유: {', '.join(reason_desc)}")
    ocr_status = str(extras.get("ocr_status", "")).upper()
    if ocr_status:
        points.append(f"OCR 상태: {_status_label(ocr_status)}")
    if ocr_status in {"FAILED", "UNREADABLE"}:
        points.append("문서 판독(OCR)에서 오류가 발생했습니다.")

    vision_status = str(extras.get("vision_status", "")).upper()
    if vision_status and vision_status != "SKIPPED":
        points.append(f"Vision 상태: {_status_label(vision_status)}")
    if vision_status == "FAILED":
        points.append("이미지 판독(Vision)에서 오류가 발생했습니다.")

    yolo_status = str(extras.get("yolo_status", "")).upper()
    if yolo_status and yolo_status != "SKIPPED":
        points.append(f"YOLO 상태: {_status_label(yolo_status)}")
    if yolo_status == "FAILED":
        points.append("인원 감지(YOLO)에서 오류가 발생했습니다.")
    if extras.get("missing_fields"):
        points.append(f"누락으로 감지된 항목: {extras['missing_fields']}")
    if extras.get("anomalies"):
        points.append(f"이상 징후: {extras['anomalies']}")
    if extras.get("violations"):
        points.append(f"위반 감지 항목: {extras['violations']}")
    if extras.get("attendance_count") and extras.get("photo_count"):
        diff = extras.get("diff", "?")
        tolerance = extras.get("tolerance", "?")
        points.append(
            f"교차 검증 불일치: 출석부 {extras['attendance_count']}명 / "
            f"사진 {extras['photo_count']}명 (차이 {diff}명, 허용 {tolerance}명)"
        )
    if extras.get("detail"):
        points.append(f"상세 내용: {extras['detail']}")
    return "\n".join(f"- {p}" for p in _dedupe_lines(points))


def _decorate_slot_extras(
    domain: str,
    slot_name: str,
    verdict: str,
    reasons: list[str],
    file_names: list[str],
    extras: dict[str, str] | None,
) -> dict[str, str]:
    out = dict(extras or {})
    reason_desc = _reason_descriptions(domain, reasons)
    if reason_desc:
        out.setdefault("reason_descriptions", ", ".join(reason_desc))
    if verdict == "PASS":
        out.setdefault("success_points", _build_success_points(domain, slot_name, file_names, out))
        if out.get("success_points"):
            out.setdefault("detail", out["success_points"].replace("- ", "").split("\n")[0])
        else:
            out.setdefault("detail", "정상")
    else:
        out.setdefault("issue_points", _build_issue_points(verdict, reason_desc, out))
        if out.get("issue_points"):
            out.setdefault("detail", out["issue_points"].replace("- ", "").split("\n")[0])
        else:
            out.setdefault("detail", "확인 필요")
    return out


def _decorate_cross_extras(
    domain: str,
    slot_name: str,
    verdict: str,
    reasons: list[str],
    extras: dict[str, str] | None,
) -> dict[str, str]:
    out = dict(extras or {})
    reason_desc = _reason_descriptions(domain, reasons)
    if reason_desc:
        out.setdefault("reason_descriptions", ", ".join(reason_desc))

    points: list[str] = []
    if verdict == "PASS":
        points.append("교차 검증이 정상 완료되었습니다.")
        if out.get("attendance_count") and out.get("photo_count"):
            points.append(
                f"출석부 {out['attendance_count']}명 / 사진 {out['photo_count']}명으로 허용 범위 내 일치했습니다."
            )
        elif out.get("month") and out.get("xlsx_total") and out.get("bill_total"):
            points.append(
                f"{out['month']} 데이터가 제출 사용량({out['xlsx_total']})과 고지서({out['bill_total']}) 기준을 충족했습니다."
            )
        if out.get("detail"):
            points.append(str(out["detail"]))
        out.setdefault("success_points", "\n".join(f"- {p}" for p in _dedupe_lines(points)))
        if out.get("success_points"):
            out.setdefault("detail", out["success_points"].replace("- ", "").split("\n")[0])
    else:
        if verdict == "NEED_FIX":
            points.append("교차 검증 항목에 수정이 필요한 문제가 있습니다.")
        else:
            points.append("교차 검증 항목에 추가 확인이 필요합니다.")
        if reason_desc:
            points.append(f"주요 사유: {', '.join(reason_desc)}")
        if out.get("attendance_count") and out.get("photo_count"):
            diff = out.get("diff", "?")
            tolerance = out.get("tolerance", "?")
            points.append(
                f"출석부 {out['attendance_count']}명 / 사진 {out['photo_count']}명 (차이 {diff}명, 허용 {tolerance}명)"
            )
        missing_required = out.get("missing_required")
        if missing_required:
            points.append(f"필수 누락 항목: {missing_required}")
        missing_optional = out.get("missing_optional")
        if missing_optional:
            points.append(f"선택 누락 항목: {missing_optional}")
        if out.get("detail"):
            points.append(f"상세 내용: {out['detail']}")
        out.setdefault("issue_points", "\n".join(f"- {p}" for p in _dedupe_lines(points)))
        if out.get("issue_points"):
            out.setdefault("detail", out["issue_points"].replace("- ", "").split("\n")[0])
    return out


def _image_format_from_ext(ext: str) -> str:
    mapping = {
        ".jpg": "jpg",
        ".jpeg": "jpg",
        ".png": "png",
        ".webp": "webp",
        ".bmp": "bmp",
        ".gif": "gif",
    }
    return mapping.get((ext or "").lower(), "png")


async def _extract_and_analyse(
    file: FileRef,
    ext: str,
    file_type: str,
    slot_name: str,
    domain: str,
    period_start: date,
    period_end: date,
    force_ocr: bool = False,
) -> dict:
    data = await download_file(file.storage_uri)
    fname = file.file_name or file.storage_uri.rsplit("/", 1)[-1]
    result: dict = {"file_id": file.file_id, "file_name": fname, "slot_name": slot_name}

    if file_type == "pdf":
        extracted = await extract_pdf(data, period_start, period_end, force_ocr=force_ocr)
        extras: dict[str, str] = {}
        try:
            raw = await ask_llm(get_prompt(PDF_ANALYSIS, domain), extracted["text"][:4000], heavy=False)
            llm = _safe_json(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            if not extracted.get("signature_detected") and llm.get("has_signature"):
                extracted["signature_detected"] = True
                extracted["reasons"] = [r for r in extracted.get("reasons", []) if r != "SIGNATURE_MISSING"]
            anomalies = llm.get("anomalies", [])
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = "; ".join(str(a) for a in anomalies)
            if llm.get("summary"):
                extras["summary"] = str(llm["summary"])
            extras.update({k: str(v) for k, v in llm.get("extras", {}).items()})
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    elif file_type == "image":
        fmt = _image_format_from_ext(ext)
        extracted = await extract_image(data, fmt, period_start, period_end)
        extras: dict[str, str] = dict(extracted.get("extras", {}))
        vision_used = False
        llm_person_count: int | None = None
        yolo_person_count: int | None = None
        is_photo_slot = slot_name.endswith(".photo")
        is_safety_ppe_slot = slot_name in {"safety.site.photos", "safety.tbm"}
        is_headcount_slot = is_photo_slot or is_safety_ppe_slot

        def _run_yolo() -> None:
            nonlocal yolo_person_count
            try:
                from app.extractors.yolo.person_counter import count_persons

                yolo_count = count_persons(data)
                yolo_person_count = int(yolo_count)
                extras["yolo_status"] = "SUCCESS"
                extras["person_count_yolo"] = str(yolo_person_count)
            except Exception as exc:
                extras.setdefault("yolo_status", "FAILED")
                extras.setdefault("yolo_error", f"{type(exc).__name__}: {exc}")

        async def _run_vision() -> None:
            nonlocal llm_person_count, vision_used
            try:
                raw = await ask_llm_vision(
                    get_prompt(IMAGE_VISION, domain),
                    get_prompt(IMAGE_VISION_USER, domain),
                    data,
                    fmt,
                )
                vision = _safe_json(raw)
                vision_used = True
                extras["vision_used"] = "true"
                extras["vision_status"] = "SUCCESS"

                for d in (vision.get("dates", []) or []):
                    if d not in extracted["dates"]:
                        extracted["dates"].append(d)
                violations = vision.get("violations", []) or vision.get("violation_list", [])
                if violations:
                    extracted.setdefault("reasons", []).append("VIOLATION_DETECTED")
                    extras["violations"] = "; ".join(str(v) for v in violations)
                non_compliant_workers = vision.get("non_compliant_workers", []) or []
                if non_compliant_workers:
                    extras["non_compliant_workers"] = json.dumps(non_compliant_workers, ensure_ascii=False)
                    if "VIOLATION_DETECTED" not in extracted.setdefault("reasons", []):
                        extracted["reasons"].append("VIOLATION_DETECTED")
                    if not extras.get("violations"):
                        extras["violations"] = f"PPE non-compliant workers: {len(non_compliant_workers)}"
                ppe_summary = vision.get("ppe_summary")
                if ppe_summary:
                    extras["ppe_summary"] = json.dumps(ppe_summary, ensure_ascii=False)

                llm_person_count = _to_int(
                    _pick_first(vision, "person_count", "personCount", "people_count", "peopleCount")
                )
                if llm_person_count is not None:
                    extras["person_count_llm"] = str(llm_person_count)

                objects = (
                    vision.get("detected_objects", [])
                    or vision.get("detectedObjects", [])
                    or vision.get("safety_objects", [])
                )
                if objects:
                    extras["detected_objects"] = ", ".join(str(o) for o in objects)
                anomalies = vision.get("anomalies", [])
                if anomalies:
                    extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                    extras["anomalies"] = "; ".join(str(a) for a in anomalies)
                scene_description = _pick_first(vision, "scene_description", "sceneDescription")
                if scene_description:
                    extras["scene_description"] = str(scene_description)
                extras.update({k: str(v) for k, v in vision.get("extras", {}).items()})
            except Exception as exc:
                extras.setdefault("vision_used", "false")
                extras.setdefault("vision_status", "FAILED")
                extras.setdefault("vision_error", f"{type(exc).__name__}: {exc}")

        if is_headcount_slot:
            # Headcount-oriented slot: YOLO first for person count.
            # For safety PPE slots, run Vision as well to evaluate PPE compliance.
            _run_yolo()
            if is_safety_ppe_slot:
                await _run_vision()
            elif yolo_person_count is None:
                await _run_vision()
            else:
                extras.setdefault("vision_used", "false")
                extras.setdefault("vision_status", "SKIPPED")
        else:
            # Non-headcount image slots should not expose Vision/YOLO failures in user-facing output.
            extras.setdefault("vision_used", "false")
            extras.setdefault("vision_status", "SKIPPED")
            extras.setdefault("yolo_status", "SKIPPED")

        if yolo_person_count is not None and llm_person_count is not None:
            extras["person_count"] = str(max(yolo_person_count, llm_person_count))
            extras["person_count_gap"] = str(abs(yolo_person_count - llm_person_count))
        elif yolo_person_count is not None:
            extras["person_count"] = str(yolo_person_count)
        elif llm_person_count is not None:
            extras["person_count"] = str(llm_person_count)

        reasons = extracted.get("reasons", [])
        if any(code in reasons for code in ("OCR_FAILED", "G_OCR_UNREADABLE")):
            has_visual_evidence = any(
                extras.get(k) for k in ("person_count", "scene_description", "detected_objects", "violations")
            )
            if has_visual_evidence:
                extracted["reasons"] = [r for r in reasons if r not in {"OCR_FAILED", "G_OCR_UNREADABLE"}]
                extras["ocr_status"] = "FALLBACK_VISION"
                extras["vision_used"] = "true"
                extras.setdefault("recognition_result", "OCR 실패로 비전 판독 결과를 대체 반영했습니다.")
            else:
                extras.setdefault("recognition_result", "OCR 판독에 실패했습니다.")
        else:
            if extras.get("ocr_status") == "SUCCESS":
                extras.setdefault("recognition_result", "OCR 판독이 완료되었습니다.")
            elif vision_used:
                extras.setdefault("recognition_result", "비전 분석으로 이미지 판독이 완료되었습니다.")

        result.update(extracted)
        result["extras"] = extras

    elif file_type == "xlsx":
        rules_mod = get_rules_module(domain)
        expected = rules_mod.EXPECTED_HEADERS.get(slot_name, [])
        extracted = await extract_xlsx(data, ext, expected, period_start, period_end)
        extras: dict[str, str] = {}
        try:
            raw = await ask_llm(get_prompt(DATA_ANALYSIS, domain), extracted["df_preview"], heavy=False)
            llm = _safe_json(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            missing = llm.get("missing_fields", [])
            if missing:
                extracted.setdefault("reasons", []).append("LLM_MISSING_FIELDS")
                extras["missing_fields"] = ", ".join(str(f) for f in missing)
            anomalies = llm.get("anomalies", [])
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = "; ".join(str(a) for a in anomalies)
            extras.update({k: str(v) for k, v in llm.get("extras", {}).items()})
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    rules_mod = get_rules_module(domain)
    allowed_reasons = set(getattr(rules_mod, "REASON_CODES", {}).keys())
    if allowed_reasons and "reasons" in result:
        result["reasons"] = [r for r in result["reasons"] if r in allowed_reasons]

    validator = _get_slot_validator(domain)
    if validator is not None:
        try:
            extra_reasons = validator.validate_slot(slot_name, file_type, result) or []
            if extra_reasons:
                result.setdefault("reasons", [])
                for r in extra_reasons:
                    if r not in result["reasons"]:
                        result["reasons"].append(r)
        except Exception:
            pass
    return result


def _validate_slot(extractions: list[dict], slot_name: str, domain: str) -> SlotResult:
    all_reasons: list[str] = []
    file_ids: list[str] = []
    file_names: list[str] = []
    extras: dict[str, str] = {}

    for ex in extractions:
        file_ids.append(ex["file_id"])
        file_names.append(ex.get("file_name", ""))
        all_reasons.extend(ex.get("reasons", []))
        extras.update(ex.get("extras", {}))

    reasons = list(dict.fromkeys(all_reasons))

    # Photo evidence should not require signatures/approval stamps.
    if slot_name.endswith(".photo") and "SIGNATURE_MISSING" in reasons:
        reasons = [r for r in reasons if r != "SIGNATURE_MISSING"]
        extras.setdefault("recognition_result", "이미지 판독이 완료되었습니다.")

    # verdict 결정 - 참고_AI_apps 기준을 유지하되 확장 reason 포함
    # A. NEED_FIX: 파일/형식 문제로 재제출 필요
    _NEED_FIX_REASONS = {
        "MISSING_SLOT",
        "PARSE_FAILED",
        "HEADER_MISMATCH",
        "EMPTY_TABLE",
        "OCR_FAILED",
    }
    # B. NEED_CLARIFY: 분석은 가능하나 확인/소명 필요
    _NEED_CLARIFY_REASONS = {
        "VIOLATION_DETECTED",
        "LOW_EDUCATION_RATE",
        "SIGNATURE_MISSING",
        "E2_SPIKE_DETECTED",
        "E3_BILL_MISMATCH",
        "LLM_ANOMALY_DETECTED",
        "G_OCR_UNREADABLE",
        "CROSS_HEADCOUNT_MISMATCH",
        "CROSS_ATTENDANCE_PARSE_FAILED",
        "CROSS_PHOTO_COUNT_FAILED",
    }

    if slot_name.endswith(".photo") and any(code in reasons for code in ("OCR_FAILED", "G_OCR_UNREADABLE")):
        vision_used = str(extras.get("vision_used", "")).lower() == "true"
        has_visual_evidence = vision_used or any(
            extras.get(k) for k in ("person_count", "scene_description", "detected_objects", "violations")
        )
        if has_visual_evidence:
            reasons = [r for r in reasons if r not in {"OCR_FAILED", "G_OCR_UNREADABLE"}]
            extras["ocr_status"] = "FALLBACK_VISION"
            extras.setdefault("recognition_result", "OCR 실패로 비전 판독 결과를 사용했습니다.")

    if any(r in _NEED_FIX_REASONS for r in reasons):
        verdict = "NEED_FIX"
    elif any(r in _NEED_CLARIFY_REASONS for r in reasons):
        verdict = "NEED_CLARIFY"
    elif reasons:
        verdict = "NEED_CLARIFY"
    else:
        verdict = "PASS"

    slots_mod = get_slots_module(domain)
    display_name_map = {s.name: s.display_name for s in slots_mod.SLOTS}
    display_name = display_name_map.get(slot_name, "")
    decorated_extras = _decorate_slot_extras(domain, slot_name, verdict, reasons, file_names, extras)

    return SlotResult(
        slot_name=slot_name,
        display_name=display_name,
        verdict=verdict,
        reasons=reasons,
        file_ids=file_ids,
        file_names=file_names,
        extras=decorated_extras,
    )


async def _generate_clarifications(slot_results: list[SlotResult], domain: str) -> list[Clarification]:
    clarifications: list[Clarification] = []

    def _friendly_evidence_lines(sr: SlotResult) -> list[str]:
        lines: list[str] = []
        reason_desc = _reason_descriptions(domain, sr.reasons)
        if reason_desc:
            lines.append(f"주요 확인 내용: {', '.join(reason_desc)}")
        if sr.extras.get("attendance_count") and sr.extras.get("photo_count"):
            lines.append(
                f"인원 교차검증: 출석부 {sr.extras['attendance_count']}명 / "
                f"사진 {sr.extras['photo_count']}명"
            )
        if sr.extras.get("diff") and sr.extras.get("tolerance"):
            lines.append(f"인원 차이: {sr.extras['diff']}명 (허용 {sr.extras['tolerance']}명)")
        if sr.extras.get("person_count"):
            lines.append(f"사진 인원 인식: {sr.extras['person_count']}명")
        if sr.extras.get("missing_fields"):
            lines.append(f"누락 항목: {sr.extras['missing_fields']}")
        if sr.extras.get("violations"):
            lines.append(f"위반 감지: {sr.extras['violations']}")
        if sr.extras.get("ocr_status"):
            lines.append(f"OCR 상태: {_status_label(str(sr.extras['ocr_status']))}")
        if sr.extras.get("vision_status"):
            lines.append(f"Vision 상태: {_status_label(str(sr.extras['vision_status']))}")
        if sr.extras.get("yolo_status"):
            lines.append(f"YOLO 상태: {_status_label(str(sr.extras['yolo_status']))}")
        if sr.extras.get("detail"):
            lines.append(f"세부 설명: {sr.extras['detail']}")
        return _dedupe_lines(lines)

    for sr in slot_results:
        reason_text = ", ".join(sr.reasons) if sr.reasons else "확인 필요"
        file_text = ", ".join(sr.file_names) if sr.file_names else "해당 파일"

        if sr.verdict == "PASS":
            slot_label = sr.display_name or sr.slot_name
            pass_points = sr.extras.get("success_points") or sr.extras.get("detail") or "필수 검증 항목을 정상 확인했습니다."
            try:
                pass_user_msg = (
                    f"슬롯: {slot_label}\n"
                    f"파일: {file_text}\n"
                    f"PASS 근거:\n{pass_points}\n"
                    "위 근거를 바탕으로 사용자에게 전달할 PASS 안내문을 한국어로 작성해 주세요."
                )
                message = await ask_llm(PASS_RESULT_TEMPLATE, pass_user_msg, heavy=False)
            except Exception:
                pass_lines = _friendly_evidence_lines(sr)
                pass_block = "\n".join(f"- {line}" for line in pass_lines) if pass_lines else "- 필수 검증 항목 확인 완료"
                message = (
                    f"{file_text} 파일의 {slot_label} 항목은 PASS로 판정되었습니다.\n"
                    f"{pass_block}"
                )
            clarifications.append(
                Clarification(
                    slot_name=sr.slot_name,
                    message=message,
                    file_ids=sr.file_ids,
                )
            )
            continue

        detail_lines: list[str] = []
        evidence_lines = _friendly_evidence_lines(sr)
        if evidence_lines:
            detail_lines.extend([f"- {line}" for line in evidence_lines])
        if sr.extras.get("issue_points"):
            detail_lines.append(f"- 점검 요약: {sr.extras['issue_points']}")
        if sr.extras.get("recognition_result"):
            detail_lines.append(f"- 판독 결과: {sr.extras['recognition_result']}")
        if sr.extras.get("ocr_status"):
            detail_lines.append(f"- OCR 상태: {_status_label(str(sr.extras['ocr_status']))}")
        if sr.extras.get("vision_status"):
            detail_lines.append(f"- Vision 상태: {_status_label(str(sr.extras['vision_status']))}")
        if sr.extras.get("yolo_status"):
            detail_lines.append(f"- YOLO 상태: {_status_label(str(sr.extras['yolo_status']))}")
        if sr.extras.get("anomalies"):
            detail_lines.append(f"- 이상 징후: {sr.extras['anomalies']}")
        if sr.extras.get("missing_fields"):
            detail_lines.append(f"- 누락 항목: {sr.extras['missing_fields']}")
        if sr.extras.get("violations"):
            detail_lines.append(f"- 위반 감지 항목: {sr.extras['violations']}")
        if sr.extras.get("summary"):
            detail_lines.append(f"- 문서 요약: {sr.extras['summary']}")
        if sr.extras.get("detected_objects"):
            detail_lines.append(f"- 감지 객체: {sr.extras['detected_objects']}")
        if sr.extras.get("detail"):
            detail_lines.append(f"- 상세: {sr.extras['detail']}")
        detail_block = "\n".join(detail_lines)

        # 참고_AI_apps 방식: reason code를 REASON_CODES 한국어 매핑과 함께 전달
        from app.engines.registry import get_rules_module as _get_rules
        try:
            _rc = getattr(_get_rules(domain), "REASON_CODES", {})
        except Exception:
            _rc = {}
        rc_text = "\n".join(f"  {k}: {v}" for k, v in _rc.items() if k in sr.reasons)

        try:
            user_msg = (
                f"슬롯: {sr.slot_name}\n"
                f"사유 코드: {reason_text}\n"
                f"REASON_CODES 매핑:\n{rc_text}\n"
                f"파일: {file_text}\n"
            )
            if detail_block:
                user_msg += f"구체적 발견 내용:\n{detail_block}\n"
            user_msg += (
                "위 내용을 바탕으로 한국어로 사용자에게 보낼 안내문을 작성해 주세요. "
                "다음 형식을 지켜 주세요: "
                "1) 검증 결과 요약 1문장, "
                "2) 확인된 근거를 불릿으로 2개 이상, "
                "3) 사용자 액션(수정/재제출/확인)을 마지막 1문장으로 안내."
            )
            message = await ask_llm(CLARIFICATION_TEMPLATE, user_msg, heavy=False)
        except Exception:
            slot_label = sr.display_name or sr.slot_name
            reason_desc = _reason_descriptions(domain, sr.reasons)
            reason_ko = ", ".join(reason_desc) if reason_desc else reason_text
            details = "\n".join(f"- {line}" for line in _friendly_evidence_lines(sr))
            action_line = (
                "- 요청 사항: 원본 파일의 해당 항목을 수정/보완한 뒤 다시 제출해 주세요."
                if sr.verdict == "NEED_FIX"
                else "- 요청 사항: 확인 가능한 근거(서명/증빙/추가 설명)를 보완해 주세요."
            )
            message = (
                f"{file_text} 파일의 {slot_label} 항목 검증 결과입니다.\n"
                f"- 판정: {sr.verdict}\n"
                f"- 사유: {reason_ko}\n"
                f"{details}\n"
                f"{action_line}"
            )

        clarifications.append(
            Clarification(
                slot_name=sr.slot_name,
                message=message,
                file_ids=sr.file_ids,
            )
        )
    return clarifications


def _base_final_extras(domain: str, overall_verdict: str, slot_results: list[SlotResult]) -> dict[str, str]:
    failing = [sr for sr in slot_results if sr.verdict != "PASS"]

    failure_codes = _dedupe_lines([r for sr in failing for r in sr.reasons])
    failure_desc = _dedupe_lines([d for sr in failing for d in _reason_descriptions(domain, sr.reasons)])
    failure_reasons = ", ".join(failure_desc or failure_codes)

    if overall_verdict == "PASS":
        recognition_result = "모든 제출 증빙의 판독이 완료되었습니다."
        failure_explanation = "실패한 판독 항목이 없습니다."
    elif overall_verdict == "NEED_FIX":
        recognition_result = "일부 증빙 판독에 실패하여 재제출이 필요합니다."
        failure_explanation = "NEED_FIX 항목이 존재하여 자동 판독 결과를 확정할 수 없습니다."
    else:
        recognition_result = "판독은 완료되었지만 확인 또는 소명이 필요한 항목이 있습니다."
        failure_explanation = "NEED_CLARIFY 항목이 존재하여 추가 확인이 필요합니다."

    detail_lines = _dedupe_lines(
        [
            f"{sr.display_name or sr.slot_name}: {sr.extras.get('detail')}"
            for sr in failing
            if sr.extras.get("detail")
        ]
    )
    if detail_lines:
        failure_explanation = "; ".join(detail_lines)

    slot_summary = " | ".join(
        _dedupe_lines(
            [
                f"{sr.display_name or sr.slot_name}={sr.verdict}"
                + (f"({','.join(sr.reasons)})" if sr.reasons else "")
                for sr in slot_results
            ]
        )
    )

    return {
        "recognition_result": recognition_result,
        "failure_reasons": failure_reasons,
        "failure_explanation": failure_explanation,
        "slot_summary": slot_summary,
    }


async def _final_aggregate(
    package_id: str,
    domain: str,
    slot_results: list[SlotResult],
    missing_slots: list[str],
    clarifications: list[Clarification],
) -> SubmitResponse:
    # missing_slots는 run_submit 단계에서 slot_results/clarifications에 반영된 상태를 기준으로 집계한다.
    _ = missing_slots

    verdicts = [sr.verdict for sr in slot_results]
    if "NEED_FIX" in verdicts:
        overall_verdict = "NEED_FIX"
        risk_level = "HIGH"
    elif "NEED_CLARIFY" in verdicts:
        overall_verdict = "NEED_CLARIFY"
        risk_level = "MEDIUM"
    else:
        overall_verdict = "PASS"
        risk_level = "LOW"

    summary_lines = []
    for sr in slot_results:
        line = f"[{sr.slot_name}] verdict={sr.verdict}, reasons={sr.reasons}"
        details = []
        for key in (
            "recognition_result",
            "ocr_status",
            "ocr_error",
            "vision_status",
            "vision_error",
            "yolo_status",
            "yolo_error",
            "person_count",
            "anomalies",
            "violations",
            "missing_fields",
        ):
            if sr.extras.get(key):
                details.append(f"{key}: {sr.extras[key]}")
        if details:
            line += f" | details: {'; '.join(details)}"
        summary_lines.append(line)
    judge_input = "\n".join(summary_lines)

    base_extras = _base_final_extras(domain, overall_verdict, slot_results)
    llm_extras: dict[str, str] = {}
    why = ""

    try:
        raw = await ask_llm(get_prompt(JUDGE_FINAL, domain), judge_input, heavy=True)
        llm_result = _safe_json(raw)
        why = str(llm_result.get("why", "")).strip()
        llm_extras = {k: str(v) for k, v in (llm_result.get("extras") or {}).items() if v is not None}
    except Exception:
        if risk_level == "HIGH":
            why = "필수 항목의 판독 실패 또는 누락이 있어 재제출이 필요합니다."
        elif risk_level == "MEDIUM":
            why = "일부 항목에 대해 추가 확인 또는 소명이 필요합니다."
        else:
            why = "모든 항목을 정상 판독했습니다."

    extras = dict(base_extras)
    for k, v in llm_extras.items():
        text = str(v).strip()
        if text:
            extras[k] = text

    for key, value in base_extras.items():
        extras.setdefault(key, value)

    if not why:
        why = extras.get("failure_explanation") or extras.get("recognition_result") or "분석이 완료되었습니다."

    return SubmitResponse(
        package_id=package_id,
        risk_level=risk_level,
        verdict=overall_verdict,
        why=why,
        slot_results=slot_results,
        clarifications=clarifications,
        extras=extras,
    )


def _run_cross_validations(
    domain: str,
    slot_groups: dict[str, list[dict]],
    period_start: date,
    period_end: date,
) -> list[dict]:
    try:
        cross_mod = importlib.import_module(f"app.engines.{domain}.cross_validators")
    except ModuleNotFoundError:
        return []

    fn = getattr(cross_mod, "cross_validate_slot", None)
    if callable(fn):
        # Support multiple signatures:
        # 1) cross_validate_slot(extractions_by_slot)
        # 2) cross_validate_slot(extractions_by_slot, period_start, period_end)
        # 3) cross_validate_slot(extractions_by_slot, period_start=..., period_end=...)
        for caller in (
            lambda: fn(dict(slot_groups), period_start=period_start, period_end=period_end),
            lambda: fn(dict(slot_groups), period_start, period_end),
            lambda: fn(dict(slot_groups)),
        ):
            try:
                result = caller()
                if isinstance(result, list):
                    return result
            except TypeError:
                continue

    legacy_fn = getattr(cross_mod, "esg_cross_checks", None)
    if callable(legacy_fn):
        try:
            result = legacy_fn(dict(slot_groups), period_start, period_end)
            if isinstance(result, list):
                return result
        except Exception:
            return []
    return []


def _resolve_submit_slot_name(
    domain: str,
    file: FileRef,
    hinted_slot: str | None,
) -> str:
    """Resolve slot for submit phase with defensive fallback.

    Priority:
    1) valid hinted slot from backend/frontend
    2) filename-based matcher from domain slots module
    3) original hinted slot (if any)
    4) "unknown"
    """
    slots_mod = get_slots_module(domain)
    known_slot_names = set(slots_mod.get_all_slot_names())

    hinted = str(hinted_slot or "").strip()
    hinted_lower = hinted.lower()
    hint_candidates: list[str] = []
    if hinted:
        hint_candidates.append(hinted)
        if hinted.endswith("_pdf"):
            hint_candidates.append(hinted[: -len("_pdf")])
        if hinted.endswith("_xlsx"):
            hint_candidates.append(hinted[: -len("_xlsx")])

    # Preview/legacy에서 내려오는 placeholder 값은 유효 슬롯 힌트로 취급하지 않는다.
    if hinted_lower in {"known", "unknown", "other", "etc"}:
        hint_candidates = []

    # Keep hint only when it is a concrete known slot.
    for cand in hint_candidates:
        if cand in known_slot_names and not cand.lower().endswith(".other"):
            return cand

    # Re-classify by filename when hint is missing/unknown/other/invalid.
    fname = file.file_name or file.storage_uri.rsplit("/", 1)[-1]
    try:
        matched = slots_mod.match_filename_to_slot(fname)
        if matched:
            slot_name, _ = matched
            if slot_name in known_slot_names:
                return slot_name
    except Exception:
        pass

    for cand in hint_candidates:
        if cand in known_slot_names:
            return cand
    return "unknown"


async def run_submit(req: SubmitRequest) -> SubmitResponse:
    triaged = triage_files(req.files)

    hint_map: dict[str, str] = {h.file_id: h.slot_name for h in req.slot_hint}
    slots_mod = get_slots_module(req.domain)
    known_slot_names = set(slots_mod.get_all_slot_names())

    resolved_items: list[tuple[dict, str]] = []
    for item in triaged:
        file = item["file"]
        hinted_slot = hint_map.get(file.file_id)
        slot_name = _resolve_submit_slot_name(req.domain, file, hinted_slot)
        resolved_items.append((item, slot_name))

    tasks = [
        _extract_and_analyse(
            file=item["file"],
            ext=item["ext"],
            file_type=item["file_type"],
            slot_name=slot_name,
            domain=req.domain,
            period_start=req.period_start,
            period_end=req.period_end,
            force_ocr=req.force_ocr,
        )
        for item, slot_name in resolved_items
    ]
    extractions = list(await asyncio.gather(*tasks))

    slot_groups: dict[str, list[dict]] = defaultdict(list)
    for ex in extractions:
        slot_groups[ex["slot_name"]].append(ex)

    slot_results = [_validate_slot(exs, sn, req.domain) for sn, exs in slot_groups.items()]

    required = slots_mod.get_required_slot_names()
    provided = {
        ex.get("slot_name", "")
        for ex in extractions
        if ex.get("slot_name") in known_slot_names
    }
    missing = [s for s in required if s not in provided]
    display_name_map = {s.name: s.display_name for s in slots_mod.SLOTS}

    # 참고_AI_apps 강점 이식: 누락 슬롯을 판정/안내문 단계에 미리 포함
    for slot_name in missing:
        missing_reasons = ["MISSING_SLOT"]
        missing_extras = _decorate_slot_extras(
            req.domain,
            slot_name,
            "NEED_FIX",
            missing_reasons,
            [],
            {"recognition_result": "필수 제출 슬롯이 누락되었습니다."},
        )
        slot_results.append(
            SlotResult(
                slot_name=slot_name,
                display_name=display_name_map.get(slot_name, ""),
                verdict="NEED_FIX",
                reasons=missing_reasons,
                file_ids=[],
                file_names=[],
                extras=missing_extras,
            )
        )

    try:
        cross_results = _run_cross_validations(req.domain, dict(slot_groups), req.period_start, req.period_end)
        cv_verdict_map = {"FAIL": "NEED_FIX", "WARN": "NEED_CLARIFY"}
        for cr in cross_results:
            raw_v = str(cr.get("verdict", "NEED_FIX"))
            mapped_v = cv_verdict_map.get(raw_v, raw_v)
            cross_slot_name = str(cr["slot_name"])
            cross_display_name = display_name_map.get(cross_slot_name, "")
            if not cross_display_name and "__x__" in cross_slot_name:
                parts = [p for p in cross_slot_name.split("__x__") if p]
                cross_display_name = " ↔ ".join(display_name_map.get(p, p) for p in parts)

            raw_reasons = [str(r) for r in (cr.get("reasons", []) or [])]
            raw_extras = {str(k): str(v) for k, v in (cr.get("extras", {}) or {}).items()}
            cross_extras = _decorate_cross_extras(
                req.domain,
                cross_slot_name,
                mapped_v,
                raw_reasons,
                raw_extras,
            )

            slot_results.append(
                SlotResult(
                    slot_name=cross_slot_name,
                    display_name=cross_display_name,
                    verdict=mapped_v,
                    reasons=raw_reasons,
                    file_ids=[],
                    file_names=[],
                    extras=cross_extras,
                )
            )
    except Exception:
        pass

    clarifications = await _generate_clarifications(slot_results, req.domain)

    return await _final_aggregate(
        package_id=req.package_id,
        domain=req.domain,
        slot_results=slot_results,
        missing_slots=missing,
        clarifications=clarifications,
    )

