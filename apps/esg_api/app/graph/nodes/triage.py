# app/graph/nodes/triage.py
'''
1) 파일 분류/검사 노드
- files의 ext/kind 표준화
- 지원하지 않는 형식/저장 실패/미존재 파일이면 issues에 FAIL 누적
'''

from __future__ import annotations
from pathlib import Path
from app.graph.state import EsgGraphState

_EXT_TO_KIND = {
    "xlsx": "XLSX",
    "xls": "XLSX",
    "pdf": "PDF",
    "png": "IMAGE",
    "jpg": "IMAGE",
    "jpeg": "IMAGE",
}

_ALLOWED_EXT = {"xlsx", "xls", "pdf", "png", "jpg", "jpeg"}

def esg_triage_node(state: EsgGraphState) -> EsgGraphState:
    files = state.get("files", []) or []

    # 이유: triage issues를 validate가 덮어쓰면 안 되므로 "누적" 시작
    issues = state.get("issues", []) or []

    normalized_files = []
    for f in files:
        file_name = f.get("file_name", "")
        ext = (f.get("ext") or Path(file_name).suffix.lower().lstrip(".")).lower()
        kind = _EXT_TO_KIND.get(ext, f.get("kind") or "UNKNOWN")

        nf = dict(f)
        nf["ext"] = ext
        nf["kind"] = kind
        normalized_files.append(nf)

        if ext not in _ALLOWED_EXT:
            issues.append({
                "level": "FAIL",
                "code": "UNSUPPORTED_FILE_EXT",
                "message": f"지원하지 않는 확장자입니다: .{ext} ({file_name})",
                "file_id": nf.get("file_id", ""),
                "evidence_ref": None,
                "slot_name": "triage",
                "meta": {"ext": ext},
            })

        fp = nf.get("file_path")
        if fp and not Path(fp).exists():
            issues.append({
                "level": "FAIL",
                "code": "FILE_NOT_FOUND",
                "message": f"저장된 파일을 찾을 수 없습니다: {fp}",
                "file_id": nf.get("file_id", ""),
                "evidence_ref": None,
                "slot_name": "triage",
                "meta": {"file_path": fp},
            })

    state["files"] = normalized_files
    state["issues"] = issues
    state["triage"] = {
        "file_count": len(normalized_files),
        "kinds": sorted(list({(f.get("kind") or "UNKNOWN") for f in normalized_files})),
        "exts": sorted(list({(f.get("ext") or "unknown") for f in normalized_files})),
    }
    return state