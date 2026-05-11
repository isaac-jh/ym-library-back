"""MCP 서버 전용 데이터베이스 모듈.

`app/` 패키지의 ORM 모델을 그대로 import 하면 PYTHONPATH 의존이
생기므로, MCP 측에서 필요한 컬럼만 가진 **읽기 전용 경량 ORM 모델**을
재정의합니다. 테이블 스키마는 `app/models/storage_catalog.py` 와
`app/models/backup_status.py` 와 동일합니다.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import get_settings


_settings = get_settings()

# pool_pre_ping: 끊긴 연결 자동 복구.
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


class StorageCatalog(Base):
    """`storage_catalog` 테이블 (읽기 전용 미러)."""

    __tablename__ = "storage_catalog"

    id = Column(Integer, primary_key=True)
    storage = Column(String(20), nullable=False)
    category = Column(String(20), nullable=False, default="ACTIVITY")
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    activity_name = Column(String(250), nullable=False)
    description = Column(String(500), nullable=True)


class BackupStatus(Base):
    """`backup_status` 테이블 (읽기 전용 미러).

    description 검색 시 `event_name`/`name` 도 함께 사용한다.
    """

    __tablename__ = "backup_status"

    id = Column(Integer, primary_key=True)
    event_name = Column(String(100), nullable=True)
    displayed_date = Column(DateTime, nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=True)
    deleted = Column(Boolean, nullable=False, default=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """`with` 문에서 사용 가능한 세션 컨텍스트 매니저.

    예외 발생 시 롤백, 정상 종료 시 자동 close.
    읽기 전용이라 commit 은 하지 않는다.
    """
    session: Session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
