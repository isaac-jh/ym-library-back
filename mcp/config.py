"""MCP 서버 설정 모듈.

`mcp/.env` 파일의 값을 Pydantic Settings 로 로드합니다.
서버/챗 앱 어디서든 :func:`get_settings` 한 번으로 동일한 설정 인스턴스를
공유합니다(LRU 캐시).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 본 파일이 있는 디렉터리 (= mcp/)
_CURRENT_DIR = Path(__file__).resolve().parent

# .env 탐색 순서: mcp/.env  →  프로젝트 루트의 .env
_CANDIDATE_ENVS = [
    _CURRENT_DIR / ".env",
    _CURRENT_DIR.parent / ".env",
]
_ENV_FILES = [str(p) for p in _CANDIDATE_ENVS if p.exists()]


class Settings(BaseSettings):
    """MCP 서버 + 챗봇 API 통합 설정.

    Attributes:
        database_url: MySQL DSN.
        google_api_key: Google AI Studio API key.
        gemma_model: 사용할 Gemma 모델 ID.
        mcp_server_name: MCP 서버에 노출되는 이름.
        chat_api_host: FastAPI 바인딩 호스트.
        chat_api_port: FastAPI 바인딩 포트.
        chat_cors_origins: CORS 허용 Origin 목록 (CSV).
    """

    database_url: str = "mysql+pymysql://root:password@localhost:3306/ym"

    google_api_key: str = Field(default="", description="Google AI Studio API key")
    gemma_model: str = Field(default="gemma-4-31b-it")

    mcp_server_name: str = "ym-library-mcp"

    chat_api_host: str = "0.0.0.0"
    chat_api_port: int = 8001
    chat_cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES if _ENV_FILES else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """`CHAT_CORS_ORIGINS` 를 리스트로 변환.

        ``"*"`` 또는 빈 값이면 모든 Origin 을 허용한다.
        """
        raw = (self.chat_cors_origins or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """캐시된 :class:`Settings` 인스턴스를 반환합니다."""
    return Settings()
