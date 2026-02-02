# AI/apps/out_risk_api/main.py

# 20260131 이종헌 수정: FastAPI 엔트리포인트 + CORS 허용 + 라우터 등록 + 헬스체크
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 수정: 루트에서 실행해도 'app.*' 임포트가 깨지지 않도록 경로 보강
import os
import sys
sys.path.append(os.path.dirname(__file__))

from app.api.risk import router as risk_router


def esg_create_app() -> FastAPI:
    # 수정: FastAPI 메타 정보 추가(디버깅/문서화 편의)
    app = FastAPI(title="out_risk_api", version="0.1.0")

    # 수정: CORS를 2번 등록하면 설정이 섞여서 디버깅이 어려움(1번만 유지)
    app.add_middleware(
        CORSMiddleware,
        # 수정: 개발용 Origin만 명시 허용(React/Streamlit)
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(risk_router, tags=["risk"])

    @app.get("/health")
    def esg_health() -> dict:
        return {"ok": True, "service": "out_risk_api"}

    return app


app = esg_create_app()
