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
        cors_allowed_origins:
            CORS 허용 Origin 목록 (CSV). 예:
            ``"https://ym-library.vercel.app,http://localhost:5173"``.
            ``credentials=True`` 와 ``"*"`` 는 함께 사용 불가 — 명시적
            도메인을 나열해야 한다.
        cors_allowed_origin_regex:
            정규식으로 매칭할 Origin 패턴. 예: Vercel preview 배포 허용
            ``r"^https://ym-library-.*\\.vercel\\.app$"``. 비어 있으면 미사용.
    """

    database_url: str = "mysql+pymysql://root:password@localhost:3306/ym"
    app_env: str = "development"
    debug: bool = True

    # ----- 카탈로그 챗봇 / MCP -----
    google_api_key: str = ""
    gemma_model: str = "gemma-4-31b-it"
    mcp_server_name: str = "ym-library-mcp"

    # ----- CORS -----
    cors_allowed_origins: str = (
        "https://ym-library.vercel.app,"
        "http://localhost:5173,"
        "http://localhost:3000"
    )
    cors_allowed_origin_regex: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """``cors_allowed_origins`` CSV 를 리스트로 변환.

        빈 항목은 제거한다. ``"*"`` 는 ``credentials=True`` 와 함께 사용 시
        starlette 가 무효화하므로 그대로 두면 헤더가 누락된다. 운영에서는
        명시 도메인만 나열할 것.
        """
        raw = (self.cors_allowed_origins or "").strip()
        if not raw:
            return []
        return [o.strip() for o in raw.split(",") if o.strip()]

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
