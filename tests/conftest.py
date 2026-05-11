"""Pytest 공용 픽스처.

테스트는 외부 MySQL 없이 인메모리 SQLite + 동일 ORM 스키마로 검증한다.
프로덕션 ORM 과 컬럼명/타입이 일치하므로, SQL 호환되는 범위에서 같은 쿼리가
동작함을 확인할 수 있다.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# `app/` 를 PYTHONPATH 에 추가해 프로덕션 코드와 동일한 import 경로를 사용.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _PROJECT_ROOT / "app"
sys.path.insert(0, str(_APP_DIR))

# DB 와 GOOGLE_API_KEY 를 테스트 전용으로 강제.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")


@pytest.fixture(scope="session", autouse=True)
def _setup_schema_and_seed():
    """세션 시작 시 인메모리 SQLite 스키마 생성 + 시드 데이터 삽입."""
    # 환경변수 적용 후에 모듈을 import 해야 한다.
    import models  # noqa: F401  (FK 관계 등록을 위해 패키지 전체 import)
    from database import Base, SessionLocal, engine
    from models.backup_status import BackupStatus
    from models.storage_catalog import StorageCatalog

    Base.metadata.create_all(engine)

    seed_catalog = [
        StorageCatalog(
            storage="NAS-A",
            category="ACTIVITY",
            year=2024,
            month=10,
            activity_name="가족초청예배(가초예)",
            description="2024년 가초예 본 영상 백업",
        ),
        StorageCatalog(
            storage="NAS-B",
            category="ACTIVITY",
            year=2025,
            month=4,
            activity_name="가족초청예배",
            description="2025년 가초예 봄 시즌",
        ),
        StorageCatalog(
            storage="CLOUD",
            category="ACTIVITY",
            year=2024,
            month=12,
            activity_name="청년부 임직예배",
            description="회중이 손을 들고 찬양하는 장면 다수 포함",
        ),
        StorageCatalog(
            storage="NAS-C",
            category="WORSHIP",
            year=2023,
            month=7,
            activity_name="여름수련회",
            description="야외 찬양",
        ),
    ]
    seed_backup = [
        BackupStatus(
            event_name="가족초청예배",
            displayed_date=datetime(2024, 10, 5),
            name="가초예 본 편집본",
            description="회중과 가족 인사 컷",
            deleted=False,
        ),
        BackupStatus(
            event_name="청년부 임직예배",
            displayed_date=datetime(2024, 12, 22),
            name="임직예배 1차 편집본",
            description="후반부 손 든 회중 컷, 통성기도 장면",
            deleted=False,
        ),
        BackupStatus(
            event_name="삭제된 이벤트",
            displayed_date=datetime(2020, 1, 1),
            name="과거 영상",
            description="손을 들고 찬양",
            deleted=True,
        ),
    ]

    session = SessionLocal()
    try:
        for row in seed_catalog + seed_backup:
            session.add(row)
        session.commit()
    finally:
        session.close()

    yield
    Base.metadata.drop_all(engine)
