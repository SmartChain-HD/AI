# app/graph/nodes/extract.py
'''
3) 값 추출 노드
- 전기(XLSX): date, electricity_kwh 컬럼 기반
  - 10/12~10/19 spike_avg
  - Q4에서 spike 제외 normal_avg
  - meta에 spike_ratio 저장
- ISO(PDF): Day3는 '존재'만 체크(향후 OCR/파싱)
- 행동강령(IMAGE): Day3는 '존재'만 체크(향후 OCR)
'''

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import pandas as pd

from app.graph.state import EsgGraphState
from app.utils.evidence import esg_make_evidence_ref


def _extract_electricity_xlsx(file_id: str, file_path: str, year_hint: int | None = None) -> dict:
    df = pd.read_excel(file_path)

    required = {"date", "electricity_kwh"}
    if not required.issubset(set(df.columns)):
        missing = sorted(list(required - set(df.columns)))
        ev = esg_make_evidence_ref(file_id=file_id, kind="XLSX", location=f"missing_columns:{','.join(missing)}")
        return {
            "file_id": file_id,
            "slot_name": "",
            "period_start": "N/A",
            "period_end": "N/A",
            "value": 0.0,
            "unit": "kWh",
            "evidence_ref": ev,
            "meta": {"error": "missing_columns", "missing": missing},
        }

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["electricity_kwh"] = pd.to_numeric(df["electricity_kwh"], errors="coerce")
    df = df.dropna(subset=["date", "electricity_kwh"]).copy()
    if df.empty:
        ev = esg_make_evidence_ref(file_id=file_id, kind="XLSX", location="no_valid_rows")
        return {
            "file_id": file_id,
            "slot_name": "",
            "period_start": "N/A",
            "period_end": "N/A",
            "value": 0.0,
            "unit": "kWh",
            "evidence_ref": ev,
            "meta": {"error": "no_valid_rows"},
        }

    # 연도 결정: 데이터 기반(우선) + 힌트(보조)
    year = int(df["date"].dt.year.mode().iloc[0])
    if year_hint and abs(year_hint - year) <= 1:
        year = year_hint

    q4_start = datetime(year, 10, 1)
    q4_end = datetime(year, 12, 31)
    spike_start = datetime(year, 10, 12)
    spike_end = datetime(year, 10, 19)

    q4_df = df[(df["date"] >= q4_start) & (df["date"] <= q4_end)].copy()
    spike_df = q4_df[(q4_df["date"] >= spike_start) & (q4_df["date"] <= spike_end)]
    normal_df = q4_df[~((q4_df["date"] >= spike_start) & (q4_df["date"] <= spike_end))]

    spike_avg = float(spike_df["electricity_kwh"].mean()) if not spike_df.empty else 0.0
    normal_avg = float(normal_df["electricity_kwh"].mean()) if not normal_df.empty else 0.0
    spike_ratio = float(spike_avg / normal_avg) if normal_avg > 0 else 0.0

    ev = esg_make_evidence_ref(
        file_id=file_id,
        kind="XLSX",
        location="sheet:* (date/electricity_kwh, Q4 baseline + spike 10/12~10/19)",
    )
    return {
        "file_id": file_id,
        "slot_name": "",
        "period_start": spike_start.strftime("%Y-%m-%d"),
        "period_end": spike_end.strftime("%Y-%m-%d"),
        "value": spike_avg,
        "unit": "kWh",
        "evidence_ref": ev,
        "meta": {
            "year": year,
            "baseline_period_start": q4_start.strftime("%Y-%m-%d"),
            "baseline_period_end": q4_end.strftime("%Y-%m-%d"),
            "normal_avg": normal_avg,
            "spike_ratio": spike_ratio,
        }
    }


def esg_extract_node(state: EsgGraphState) -> EsgGraphState:
    extracted: list[dict] = []
    files_by_id = {f["file_id"]: f for f in state.get("files", []) or []}

    for m in state.get("slot_map", []) or []:
        fid = m.get("file_id")
        slot = m.get("slot_name")
        f = files_by_id.get(fid or "")
        if not f:
            continue

        kind = f.get("kind")
        file_path = f.get("file_path", "")

        if slot in ["electricity_usage_2024", "electricity_usage_2025"] and kind == "XLSX":
            year_hint = 2024 if slot.endswith("2024") else 2025
            item = _extract_electricity_xlsx(fid, file_path, year_hint=year_hint)
            item["slot_name"] = slot
            extracted.append(item)

        elif slot == "iso_45001" and kind == "PDF":
            ev = esg_make_evidence_ref(file_id=fid, kind="PDF", location="page:1 (demo_exists)")
            extracted.append({
                "file_id": fid,
                "slot_name": slot,
                "period_start": "N/A",
                "period_end": "N/A",
                "value": 1.0,
                "unit": "doc_exists",
                "evidence_ref": ev,
                "meta": {"note": "Day3: pdf existence only (parsing later)"},
            })

        elif slot == "code_of_conduct" and kind == "IMAGE":
            ev = esg_make_evidence_ref(file_id=fid, kind="IMAGE", location="page:1 bbox:(demo_placeholder)")
            extracted.append({
                "file_id": fid,
                "slot_name": slot,
                "period_start": "N/A",
                "period_end": "N/A",
                "value": 1.0,
                "unit": "doc_exists",
                "evidence_ref": ev,
                "meta": {"note": "Day3: image existence only (OCR later)"},
            })

    state["extracted"] = extracted
    return state