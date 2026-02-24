# app/engines/esg/cross_validators.py

"""
ESG cross validators
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from app.engines.esg.validators import (
    _esg_read_df,
)


def _parse_date_any(text: str) -> date | None:
    """YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD"""
    if not text:
        return None
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _parse_bill_fields(pdf_text: str) -> dict[str, Any]:
    """고지서 PDF에서 당월 사용량과 청구 기간을 추출한다."""
    out: dict[str, Any] = {
        "bill_total": None,
        "bill_unit": None,
        "bill_period_start": None,
        "bill_period_end": None,
    }
    if not pdf_text:
        return out

    m = re.search(
        r"(?:당월\s*사용량|사용량|usage)\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(kwh|m3|m³|㎥|톤|ton|t)",
        pdf_text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"([\d,]+(?:\.\d+)?)\s*(kwh|m3|m³|㎥|톤|ton|t)",
            pdf_text,
            re.IGNORECASE,
        )
    if m:
        out["bill_total"] = float(m.group(1).replace(",", ""))
        out["bill_unit"] = m.group(2)
    m2 = re.search(
        r"(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})\s*[~\-]\s*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})",
        pdf_text,
    )
    if m2:
        out["bill_period_start"] = _parse_date_any(m2.group(1))
        out["bill_period_end"] = _parse_date_any(m2.group(2))
    return out


def _pick_first(extractions_by_slot: dict[str, list[dict]], candidates: set[str]) -> dict | None:
    for s in candidates:
        xs = extractions_by_slot.get(s) or []
        if xs:
            return xs[0]
    return None


def _pick_all(extractions_by_slot: dict[str, list[dict]], candidates: set[str]) -> list[dict]:
    out: list[dict] = []
    for s in candidates:
        out += (extractions_by_slot.get(s) or [])
    return out


def _daily_peak(df: pd.DataFrame, time_col: str, value_col: str) -> float | None:
    try:
        if time_col not in df.columns:
          for c in ("date", "timestamp", "datetime", "ts", "time", "일자", "날짜"):
            if c in df.columns:
                time_col = c
                break
        if value_col not in df.columns:
            for c in ("Usage_kWh", "usage_kwh", "kwh", "flow_m3", "usage_m3", "Usage_m3", "m3", "㎥", "사용량"):
                if c in df.columns:
                    value_col = c
                    break
        ts = pd.to_datetime(df[time_col], errors="coerce")
        v = pd.to_numeric(df[value_col], errors="coerce")
        tmp = pd.DataFrame({"ts": ts, "v": v}).dropna()
        if tmp.empty:
            return None
        tmp["d"] = tmp["ts"].dt.date
        daily = tmp.groupby("d")["v"].sum()
        if daily.empty:
            return None
        return float(daily.max())
    except Exception:
        return None


def _monthly_sum(df: pd.DataFrame, time_col: str, value_col: str) -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = {}
    try:
        if time_col not in df.columns:
          for c in ("date", "timestamp", "datetime", "ts", "time", "일자", "날짜"):
              if c in df.columns:
                  time_col = c
                  break
        if value_col not in df.columns:
            for c in ("Usage_kWh", "usage_kwh", "kwh", "flow_m3", "usage_m3", "Usage_m3", "m3", "㎥", "사용량"):
                if c in df.columns:
                    value_col = c
                    break
        ts = pd.to_datetime(df[time_col], errors="coerce")
        v = pd.to_numeric(df[value_col], errors="coerce")
        tmp = pd.DataFrame({"ts": ts, "v": v}).dropna()
        if tmp.empty:
            return out
        tmp["y"] = tmp["ts"].dt.year
        tmp["m"] = tmp["ts"].dt.month
        g = tmp.groupby(["y", "m"])["v"].sum()
        for (y, m), total in g.items():
            out[(int(y), int(m))] = float(total)
        return out
    except Exception:
        return out


def _bill_month_key(fields: dict[str, Any]) -> tuple[int, int] | None:
    d = fields.get("bill_period_end") or fields.get("bill_period_start")
    if not d:
        return None
    return (int(d.year), int(d.month))


def _compare_month_total(slot_name: str, xlsx_total: float | None, bill_total: float | None, tol_pct: float, month: str) -> dict[str, Any]:
    if xlsx_total is None or bill_total is None or bill_total <= 0:
        return {
            "slot_name": slot_name,
            "reasons": ["E3_BILL_FIELDS_MISSING"],
            "verdict": "NEED_FIX",
            "extras": {"month": month},
        }

    diff_pct = abs(xlsx_total - bill_total) / bill_total * 100.0
    verdict = "PASS"
    reasons: list[str] = []

    if diff_pct > tol_pct:
        reasons.append("E3_BILL_MISMATCH")
        verdict = "FAIL" if diff_pct >= 20.0 else "NEED_FIX"

    return {
        "slot_name": slot_name,
        "reasons": reasons,
        "verdict": verdict,
        "extras": {
            "month": month,
            "xlsx_total": round(float(xlsx_total), 3),
            "bill_total": round(float(bill_total), 3),
            "diff_pct": round(float(diff_pct), 2),
            "tol_pct": tol_pct,
        },
    }


def _parse_disposal_list(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    cols = {c: c.lower() for c in df.columns}

    def pick(*keys: str) -> str | None:
        for c, lc in cols.items():
            if any(k in lc for k in keys):
                return c
        return None

    col_name = pick("물질", "material", "item", "품명", "name")
    col_qty = pick("수량", "톤", "qty", "quantity", "amount")
    col_date = pick("일자", "날짜", "date", "처리일", "배출일")

    if not col_name or not col_date:
        return []

    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        name = str(row.get(col_name, "")).strip()
        d = str(row.get(col_date, "")).strip()
        if not name or not d:
            continue
        out.append({
            "name": name,
            "date_raw": d,
            "qty_raw": str(row.get(col_qty, "")).strip() if col_qty else "",
        })
    return out


def _disposal_evidence_probe(pdf_text: str) -> dict[str, Any]:
    if not pdf_text:
        return {"has_date": False, "has_qty": False, "has_company": False}

    has_date = bool(re.search(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", pdf_text))
    has_qty = bool(re.search(r"([\d,]+)\s*(kg|톤|t|l|L|m3|m³)", pdf_text, re.IGNORECASE))
    has_company = bool(re.search(r"(주식회사|㈜|처리업체|수거|운반|위탁)", pdf_text))
    return {"has_date": has_date, "has_qty": has_qty, "has_company": has_company}


def _inventory_chemicals(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    name_col = "물질명" if "물질명" in df.columns else None
    req_col = "MSDS_필수" if "MSDS_필수" in df.columns else None

    if not name_col:
        return []

    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        name = str(row.get(name_col, "")).strip()
        if not name:
            continue
        msds_req = str(row.get(req_col, "Y")).strip().upper() if req_col else "Y"
        out.append({"name": name, "msds_required": msds_req == "Y"})
    return out


def _msds_coverage(chemicals: list[dict[str, Any]], msds_docs: list[dict]) -> tuple[list[str], list[str]]:
    msds_text_all = " ".join([(d.get("text", "") or "") for d in msds_docs]).lower()
    msds_names_all = " ".join([(d.get("file_name", "") or d.get("source_file_name", "") or "") for d in msds_docs]).lower()

    missing_required: list[str] = []
    missing_optional: list[str] = []

    for c in chemicals:
        nm = c["name"].lower()
        hit = (nm in msds_text_all) or (nm in msds_names_all)
        if hit:
            continue
        if c["msds_required"]:
            missing_required.append(c["name"])
        else:
            missing_optional.append(c["name"])

    return missing_required, missing_optional


def _fmt_num(v: float | None) -> str:
    if v is None:
        return "N/A"
    s = f"{float(v):.3f}"
    s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def esg_cross_checks(
    extractions_by_slot: dict[str, list[dict]],
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:

    out: list[dict[str, Any]] = []

    ELEC_USAGE = {"esg.energy.electricity.usage_xlsx", "esg.energy.electricity.usage"}
    GAS_USAGE = {"esg.energy.gas.usage_xlsx", "esg.energy.gas.usage"}
    WATER_USAGE = {"esg.energy.water.usage_xlsx", "esg.energy.water.usage"}

    ELEC_BILL = {"esg.energy.electricity.bill_pdf", "esg.energy.electricity.bill"}
    GAS_BILL = {"esg.energy.gas.bill_pdf", "esg.energy.gas.bill"}
    WATER_BILL = {"esg.energy.water.bill_pdf", "esg.energy.water.bill"}

    INV = {"esg.hazmat.inventory_xlsx", "esg.hazmat.inventory"}
    MSDS = {"esg.hazmat.msds_pdf", "esg.hazmat.msds"}

    WASTE_LIST = {"esg.hazmat.disposal.list_xlsx", "esg.hazmat.disposal.list"}
    WASTE_EVI = {"esg.hazmat.disposal.evidence_pdf", "esg.hazmat.disposal.evidence"}

    ETHICS_LATEST = {"esg.governance.ethics.latest_pdf"}
    PLEDGE = {"esg.governance.pledge_pdf", "esg.ethics.pledge"}

    # Cross-1) 10/11/12월 사용량 vs 고지서 사용량 교차검증
    # - 전력 피크(2024 대비 2025) 비교는 제외한다.
    def cross_month_match(
        usage_candidates: set[str],
        bill_candidates: set[str],
        time_col: str,
        val_col: str,
        out_slot: str,
        tol_pct: float,
    ) -> None:
        usage = _pick_first(extractions_by_slot, usage_candidates)
        bills = _pick_all(extractions_by_slot, bill_candidates)

        if not usage and not bills:
            out.append({
                "slot_name": out_slot,
                "reasons": ["E3_BILL_FIELDS_MISSING"],
                "verdict": "NEED_FIX",
                "extras": {"detail": "사용량 파일과 고지서 파일이 모두 누락되었습니다."},
            })
            return
        if not usage:
            out.append({
                "slot_name": out_slot,
                "reasons": ["E3_BILL_FIELDS_MISSING"],
                "verdict": "NEED_FIX",
                "extras": {"detail": "사용량 파일이 누락되어 10~12월 교차검증을 수행할 수 없습니다."},
            })
            return
        if not bills:
            out.append({
                "slot_name": out_slot,
                "reasons": ["E3_BILL_FIELDS_MISSING"],
                "verdict": "NEED_FIX",
                "extras": {"detail": "요금 고지서 파일이 누락되어 10~12월 교차검증을 수행할 수 없습니다."},
            })
            return

        df = _esg_read_df(usage.get("df_full") or usage.get("df_preview", ""))
        if df.empty:
            out.append({
                "slot_name": out_slot,
                "reasons": ["PARSE_FAILED"],
                "verdict": "NEED_FIX",
                "extras": {
                    "detail": f"사용량 파일 파싱에 실패했습니다. '{time_col}' 및 '{val_col}' 계열 컬럼을 확인해 주세요.",
                },
            })
            return

        month_sum = _monthly_sum(df, time_col, val_col)
        if not month_sum:
            out.append({
                "slot_name": out_slot,
                "reasons": ["PARSE_FAILED"],
                "verdict": "NEED_FIX",
                "extras": {
                    "detail": f"사용량 월합계를 계산하지 못했습니다. '{time_col}' 및 '{val_col}' 계열 컬럼을 확인해 주세요.",
                },
            })
            return

        bill_by_month: dict[tuple[int, int], float] = {}
        bill_parse_fail = 0
        for b in bills:
            fields = _parse_bill_fields(b.get("text", ""))
            mk = _bill_month_key(fields)
            bill_total = fields.get("bill_total")
            if not mk or bill_total is None:
                bill_parse_fail += 1
                continue
            bill_by_month[mk] = float(bill_total)

        if not bill_by_month:
            out.append({
                "slot_name": out_slot,
                "reasons": ["E3_BILL_FIELDS_MISSING"],
                "verdict": "NEED_FIX",
                "extras": {"detail": "고지서에서 기간 또는 당월 사용량을 추출하지 못했습니다."},
            })
            return

        usage_years = sorted({y for y, _ in month_sum.keys()})
        bill_years = sorted({y for y, _ in bill_by_month.keys()})
        target_year = int(period_end.year if period_end else period_start.year)
        if usage_years and target_year not in usage_years:
            target_year = usage_years[-1]
        elif not usage_years and bill_years and target_year not in bill_years:
            target_year = bill_years[-1]

        target_months = (10, 11, 12)
        reasons: list[str] = []
        month_lines: list[str] = []
        verdict = "PASS"

        for m in target_months:
            mk = (target_year, m)
            month_str = f"{target_year}-{m:02d}"
            xlsx_total = month_sum.get(mk)
            bill_total = bill_by_month.get(mk)

            if xlsx_total is None or bill_total is None or bill_total <= 0:
                reasons.append("E3_BILL_FIELDS_MISSING")
                verdict = "NEED_FIX"
                month_lines.append(
                    f"{month_str} 누락(사용량={_fmt_num(xlsx_total)}, 고지서={_fmt_num(bill_total)})"
                )
                continue

            diff_pct = abs(float(xlsx_total) - float(bill_total)) / float(bill_total) * 100.0
            if diff_pct > tol_pct:
                reasons.append("E3_BILL_MISMATCH")
                verdict = "NEED_FIX"
                month_lines.append(
                    f"{month_str} 불일치(사용량={_fmt_num(xlsx_total)}, 고지서={_fmt_num(bill_total)}, 차이={diff_pct:.2f}%, 허용={tol_pct:.2f}%)"
                )
            else:
                month_lines.append(
                    f"{month_str} 일치(사용량={_fmt_num(xlsx_total)}, 고지서={_fmt_num(bill_total)}, 차이={diff_pct:.2f}%)"
                )

        if bill_parse_fail:
            month_lines.append(f"고지서 {bill_parse_fail}건은 기간/사용량 파싱에 실패했습니다.")

        out.append({
            "slot_name": out_slot,
            "reasons": list(dict.fromkeys(reasons)),
            "verdict": verdict,
            "extras": {
                "target_year": str(target_year),
                "target_months": f"{target_year}-10,{target_year}-11,{target_year}-12",
                "detail": "; ".join(month_lines),
            },
        })

    cross_month_match(ELEC_USAGE, ELEC_BILL, "date", "Usage_kWh", "esg.energy.electricity.month_match", 1.0)
    cross_month_match(GAS_USAGE, GAS_BILL, "timestamp", "flow_m3", "esg.energy.gas.month_match", 2.0)
    cross_month_match(WATER_USAGE, WATER_BILL, "timestamp", "Usage_m3", "esg.energy.water.month_match", 1.0)

    waste_list = _pick_first(extractions_by_slot, WASTE_LIST)
    waste_evi = _pick_first(extractions_by_slot, WASTE_EVI)

    if waste_list or waste_evi:
        if not waste_list or not waste_evi:
            out.append({
                "slot_name": "esg.hazmat.disposal.cross_check",
                "reasons": ["E_WASTE_EVIDENCE_MISSING"],
                "verdict": "NEED_FIX",
                "extras": {},
            })
        else:
            df = _esg_read_df(waste_list.get("df_full") or waste_list.get("df_preview", ""))
            items = _parse_disposal_list(df)
            probe = _disposal_evidence_probe(waste_evi.get("text", ""))

            reasons: list[str] = []
            verdict = "PASS"

            if not items:
                reasons.append("E_WASTE_LIST_PARSE_FAILED")
                verdict = "NEED_FIX"

            if not (probe["has_date"] and probe["has_qty"] and probe["has_company"]):
                reasons.append("E_WASTE_EVIDENCE_FIELDS_WEAK")
                verdict = "NEED_FIX"

            pdf_text = (waste_evi.get("text", "") or "").lower()
            missing_names: list[str] = []
            for it in items[:10]:
                if it["name"].lower() not in pdf_text:
                    missing_names.append(it["name"])

            if missing_names:
                reasons.append("E_WASTE_NAME_MISMATCH")
                verdict = "FAIL"

            out.append({
                "slot_name": "esg.hazmat.disposal.cross_check",
                "reasons": list(dict.fromkeys(reasons)),
                "verdict": verdict,
                "extras": {"missing_names": missing_names},
            })

    inv = _pick_first(extractions_by_slot, INV)
    msds_docs = _pick_all(extractions_by_slot, MSDS)

    if inv:
        df = _esg_read_df(inv.get("df_full") or inv.get("df_preview", ""))
        chems = _inventory_chemicals(df)

        if not chems:
            out.append({
                "slot_name": "esg.hazmat.msds.coverage",
                "reasons": ["E_INVENTORY_PARSE_FAILED"],
                "verdict": "NEED_FIX",
                "extras": {},
            })
        else:
            missing_req, missing_opt = _msds_coverage(chems, msds_docs)
            reasons: list[str] = []
            verdict = "PASS"

            if missing_req:
                reasons.append("E_MSDS_MISSING_REQUIRED")
                verdict = "FAIL"
            elif missing_opt:
                reasons.append("E_MSDS_MISSING_OPTIONAL")
                verdict = "WARN"

            out.append({
                "slot_name": "esg.hazmat.msds.coverage",
                "reasons": reasons,
                "verdict": verdict,
                "extras": {"missing_required": missing_req, "missing_optional": missing_opt},
            })

    ethics_latest = _pick_first(extractions_by_slot, ETHICS_LATEST)
    pledge = _pick_first(extractions_by_slot, PLEDGE)

    if ethics_latest and pledge:
        rev = _parse_date_any(ethics_latest.get("text", ""))
        pled = _parse_date_any(pledge.get("text", ""))
        if rev and pled and pled < rev:
            out.append({
                "slot_name": "esg.governance.pledge_check",
                "reasons": ["E9_PLEDGE_BEFORE_REVISION"],
                "verdict": "WARN",
                "extras": {"revision_date": str(rev), "pledge_date": str(pled)},
            })

    return out


def cross_validate_slot(
    extractions_by_slot: dict[str, list[dict]],
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict[str, Any]]:
    """Compatibility wrapper used by submit pipeline."""
    today = date.today()
    return esg_cross_checks(
        extractions_by_slot=extractions_by_slot,
        period_start=period_start or today,
        period_end=period_end or today,
    )

