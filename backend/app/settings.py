from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "SurveyGen"
    database_url: str = "sqlite+aiosqlite:///./backend/app.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    arxiv_proxy: str = ""
    arxiv_timeout_seconds: float = 15.0
    secret_key: str = "survey2-local-dev-secret"

    storage_root: str = "D:/survey2_storage"

    translation_provider: str = "volcengine"
    translation_fallback_to_llm: bool = True
    volc_access_key_id: str = ""
    volc_secret_access_key: str = ""
    volc_region: str = "cn-north-1"
    volc_translate_source_language: str = "en"
    volc_translate_target_language: str = "zh"
    volc_translate_max_chars: int = 4000
    volc_translate_concurrency: int = 5


settings = Settings()

