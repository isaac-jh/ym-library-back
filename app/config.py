"""
애플리케이션 설정 모듈

환경 변수를 로드하고 애플리케이션 설정을 관리합니다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 현재 파일 위치 기준 디렉토리
CURRENT_DIR = Path(__file__).resolve().parent

# .env 파일 경로 탐색 (Docker와 로컬 환경 모두 지원)
# 1. 현재 디렉토리 (Docker: /app/.env)
# 2. 부모 디렉토리 (로컬: project_root/.env)
ENV_FILE = CURRENT_DIR / ".env"
if not ENV_FILE.exists():
    ENV_FILE = CURRENT_DIR.parent / ".env"


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스

    환경 변수에서 설정 값을 로드합니다.
    .env 파일에서 자동으로 값을 읽어옵니다.

    Attributes:
        database_url: MySQL 데이터베이스 연결 URL
        app_env: 애플리케이션 환경 (development, production, test)
        debug: 디버그 모드 활성화 여부
        google_api_key: Google AI Studio API Key (Gemma 호출용)
        gemma_model: 사용할 Gemma 모델 ID (기본: gemma-4-31b-it)
        mcp_server_name: MCP stdio 서버 표시 이름
    """

    database_url: str = "mysql+pymysql://root:password@localhost:3306/ym"
    app_env: str = "development"
    debug: bool = True

    # ----- 카탈로그 챗봇 / MCP -----
    google_api_key: str = ""
    gemma_model: str = "gemma-4-31b-it"
    mcp_server_name: str = "ym-library-mcp"

    # Pydantic v2 설정 방식
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",  # .env에 정의되지 않은 변수 무시
    )


@lru_cache()
def get_settings() -> Settings:
    """
    설정 인스턴스를 반환합니다.

    캐싱을 통해 애플리케이션 전체에서 동일한 설정 인스턴스를 사용합니다.

    Returns:
        Settings: 애플리케이션 설정 인스턴스
    """
    return Settings()
