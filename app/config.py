"""
애플리케이션 설정 모듈

환경 변수를 로드하고 애플리케이션 설정을 관리합니다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 디렉토리 경로
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스

    환경 변수에서 설정 값을 로드합니다.
    .env 파일에서 자동으로 값을 읽어옵니다.

    Attributes:
        database_url: MySQL 데이터베이스 연결 URL
        app_env: 애플리케이션 환경 (development, production, test)
        debug: 디버그 모드 활성화 여부
    """

    database_url: str = "mysql+pymysql://root:password@localhost:3306/ym"
    app_env: str = "development"
    debug: bool = True

    # Pydantic v2 설정 방식
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
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
