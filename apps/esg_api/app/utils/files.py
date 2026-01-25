# app/utils/files.py
'''
업로드 파일 저장 유틸
UploadFile → 로컬 저장 + file_id 부여 + file_path/ext/kind 반환
'''

from __future__ import annotations
from pathlib import Path
from fastapi import UploadFile
import uuid


def esg_get_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "AI").exists():
            return p
    return Path.cwd().resolve()


def esg_get_upload_dir() -> Path:
    repo_root = esg_get_repo_root()
    upload_dir = repo_root / "AI" / "apps" / "esg_api" / "data" / "outputs"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def esg_guess_kind(ext: str) -> str:
    ext = (ext or "").lower().lstrip(".")
    if ext in ["xlsx", "xls"]:
        return "XLSX"
    if ext in ["pdf"]:
        return "PDF"
    if ext in ["png", "jpg", "jpeg"]:
        return "IMAGE"
    return "UNKNOWN"


def esg_save_uploads(files: list[UploadFile]) -> list[dict]:
    out_dir = esg_get_upload_dir()
    saved: list[dict] = []

    for f in files:
        file_id = uuid.uuid4().hex[:12]
        name = f.filename or f"{file_id}.bin"
        ext = (Path(name).suffix or "").lower().lstrip(".")
        kind = esg_guess_kind(ext)

        path = out_dir / f"{file_id}_{name}"

        # 이유: UploadFile 스트림은 한번 읽으면 포인터가 끝으로 감.
        # 재시도/테스트/다중 read 대비해서 seek(0) 해주는 게 안전.
        try:
            f.file.seek(0)
        except Exception:
            pass

        content = f.file.read()
        with path.open("wb") as w:
            w.write(content)

        saved.append({
            "file_id": file_id,
            "file_name": name,
            "file_path": str(path),
            "ext": ext,
            "kind": kind,
        })

    print(f"[upload] saved {len(saved)} file(s) into: {out_dir.resolve()}")
    return saved