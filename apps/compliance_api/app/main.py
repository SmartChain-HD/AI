from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.review import router as review_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

# CORS 설정: 프론트엔드 연동용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(review_router, prefix="/api/v1/review", tags=["Compliance Review"])

@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}