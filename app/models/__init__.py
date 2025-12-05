"""
데이터베이스 모델 패키지

모든 SQLAlchemy 모델을 이 패키지에서 관리합니다.

주의: import 순서가 중요합니다.
- User가 먼저 로드되어야 다른 모델에서 FK 참조 가능
- BackupStatus는 User를 참조
- MUserBackupStatus는 User와 BackupStatus를 모두 참조
"""

# 순환 참조 방지를 위해 순서대로 import
from models.user import User
from models.storage_catalog import StorageCatalog
from models.backup_status import BackupStatus
from models.m_user_backup_status import MUserBackupStatus

__all__ = [
    "User",
    "StorageCatalog",
    "BackupStatus",
    "MUserBackupStatus",
]
