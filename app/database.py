"""
데이터베이스 연결 모듈

SQLAlchemy를 사용하여 MySQL 데이터베이스 연결을 설정합니다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

settings = get_settings()

# SQLAlchemy 엔진 생성
# pool_pre_ping: 연결 유효성 검사를 위해 사용
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,  # SQL 쿼리 로깅 (디버그 모드에서만)
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모델 베이스 클래스
Base = declarative_base()


def get_db():
    """
    데이터베이스 세션을 생성하고 반환하는 의존성 함수

    FastAPI의 Depends에서 사용됩니다.
    요청이 완료되면 세션을 자동으로 닫습니다.

    Yields:
        Session: SQLAlchemy 데이터베이스 세션
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
