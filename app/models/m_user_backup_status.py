"""
작업자 매핑 모델

사용자와 백업 상태 간의 매핑 관계를 관리합니다.
어떤 작업자가 어떤 백업 작업에 참여했는지 기록합니다.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from database import Base


class MUserBackupStatus(Base):
    """
    사용자-백업상태 매핑 테이블 모델

    작업자와 백업 상태 간의 다대다 관계를 관리하는 매핑 테이블입니다.

    Attributes:
        id: 고유 식별자 (자동 증가)
        user_id: 사용자 ID (외래키)
        backup_status_id: 백업 상태 ID (외래키)
        created_at: 생성 일시
        created_by: 생성자 ID (외래키)
    """

    __tablename__ = "m_user_backup_status"
    __table_args__ = {"comment": "작업자 매핑 테이블"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="고유 식별자")
    user_id = Column(
        Integer, ForeignKey("user.id"), nullable=False, comment="사용자 ID"
    )
    backup_status_id = Column(
        Integer, ForeignKey("backup_status.id"), nullable=False, comment="백업 상태 ID"
    )
    created_at = Column(
        DateTime, nullable=True, default=datetime.utcnow, comment="생성 일시"
    )
    created_by = Column(
        Integer, ForeignKey("user.id"), nullable=False, comment="생성자 ID"
    )

    # 관계 설정 - foreign_keys를 명시적으로 지정
    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="backup_status_mappings",
    )
    backup_status = relationship(
        "BackupStatus",
        back_populates="user_mappings",
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_mappings",
    )

    def __repr__(self) -> str:
        """모델의 문자열 표현을 반환합니다."""
        return (
            f"<MUserBackupStatus(id={self.id}, user_id={self.user_id}, "
            f"backup_status_id={self.backup_status_id})>"
        )
