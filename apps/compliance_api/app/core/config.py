# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    CLOVA_INVOKE_URL: str
    CLOVA_OCR_SECRET: str
    ENVIRONMENT: str = "development"
    APP_NAME: str = "Compliance AI Reviewer"
    
    # .env 파일에서 읽어옴 (extra='ignore'로 불필요한 값 무시)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()