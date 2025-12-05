"""
사용자 모델

시스템 사용자 정보를 관리합니다.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    """
    사용자 테이블 모델

    시스템에 등록된 사용자 정보를 저장하는 테이블입니다.

    Attributes:
        id: 고유 식별자 (자동 증가)
        name: 사용자 이름
        nickname: 닉네임
        password: 암호화된 비밀번호
        deleted: 삭제 여부 (소프트 삭제)
        created_at: 생성 일시
    """

    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="고유 식별자")
    name = Column(String(10), nullable=False, comment="사용자 이름")
    nickname = Column(String(200), nullable=False, comment="닉네임")
    password = Column(String(500), nullable=False, comment="암호화된 비밀번호")
    deleted = Column(Boolean, nullable=False, default=False, comment="삭제 여부")
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, comment="생성 일시"
    )

    # 작업자 매핑 관계 (user_id 기준)
    # MUserBackupStatus에 user_id와 created_by 두 개의 FK가 있으므로 명시적 지정 필요
    backup_status_mappings = relationship(
        "MUserBackupStatus",
        foreign_keys="MUserBackupStatus.user_id",
        back_populates="user",
    )

    # 내가 생성한 매핑 관계 (created_by 기준)
    created_mappings = relationship(
        "MUserBackupStatus",
        foreign_keys="MUserBackupStatus.created_by",
        back_populates="creator",
    )

    def __repr__(self) -> str:
        """모델의 문자열 표현을 반환합니다."""
        return f"<User(id={self.id}, name='{self.name}', nickname='{self.nickname}')>"

    @property
    def is_active(self) -> bool:
        """
        사용자 활성 상태를 확인합니다.

        Returns:
            bool: 삭제되지 않은 활성 사용자인지 여부
        """
        return not self.deleted
