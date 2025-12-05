"""
백업 상태 모델

미디어 백업 진행 상태를 추적하고 관리합니다.
카메라 원본, 마스터, 정리본, 최종 산출물의 백업 여부를 기록합니다.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class BackupStatus(Base):
    """
    백업 상태 테이블 모델

    각 이벤트/콘텐츠의 백업 진행 상태를 추적하는 테이블입니다.

    Attributes:
        id: 고유 식별자 (자동 증가)
        event_name: 이벤트명
        displayed_date: 표시 날짜
        name: 콘텐츠/파일 이름
        description: 상세 설명
        cam: 카메라 원본 백업 여부
        cam_checker: 카메라 원본 확인자 (User ID)
        master: 마스터 파일 백업 여부
        master_checker: 마스터 파일 확인자 (User ID)
        clean: 정리본 백업 여부
        clean_checker: 정리본 확인자 (User ID)
        final_product: 최종 산출물 백업 여부
        final_product_checker: 최종 산출물 확인자 (User ID)
        deleted: 삭제 여부 (소프트 삭제)
        deleted_by: 삭제한 사용자 ID
        created_at: 생성 일시
    """

    __tablename__ = "backup_status"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="고유 식별자")
    event_name = Column(String(100), nullable=True, comment="이벤트명")
    displayed_date = Column(DateTime, nullable=True, comment="표시 날짜")
    name = Column(String(100), nullable=False, comment="콘텐츠/파일 이름")
    description = Column(String(1000), nullable=True, comment="상세 설명")
    cam = Column(Boolean, nullable=True, comment="카메라 원본 백업 여부")
    cam_checker = Column(
        Integer, ForeignKey("user.id"), nullable=True, comment="카메라 원본 확인자"
    )
    master = Column(Boolean, nullable=True, comment="마스터 파일 백업 여부")
    master_checker = Column(
        Integer, ForeignKey("user.id"), nullable=True, comment="마스터 파일 확인자"
    )
    clean = Column(Boolean, nullable=True, comment="정리본 백업 여부")
    clean_checker = Column(
        Integer, ForeignKey("user.id"), nullable=True, comment="정리본 확인자"
    )
    final_product = Column(Boolean, nullable=True, comment="최종 산출물 백업 여부")
    final_product_checker = Column(
        Integer, ForeignKey("user.id"), nullable=True, comment="최종 산출물 확인자"
    )
    deleted = Column(
        Boolean, nullable=False, default=False, comment="삭제 여부 (소프트 삭제)"
    )
    deleted_by = Column(
        Integer, ForeignKey("user.id"), nullable=True, comment="삭제한 사용자 ID"
    )
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, comment="생성 일시"
    )

    # 관계 설정
    cam_checker_user = relationship(
        "User", foreign_keys=[cam_checker], backref="cam_checked_backups"
    )
    master_checker_user = relationship(
        "User", foreign_keys=[master_checker], backref="master_checked_backups"
    )
    clean_checker_user = relationship(
        "User", foreign_keys=[clean_checker], backref="clean_checked_backups"
    )
    final_product_checker_user = relationship(
        "User",
        foreign_keys=[final_product_checker],
        backref="final_product_checked_backups",
    )
    deleted_by_user = relationship(
        "User", foreign_keys=[deleted_by], backref="deleted_backups"
    )

    # 작업자 매핑 관계
    user_mappings = relationship("MUserBackupStatus", back_populates="backup_status")

    def __repr__(self) -> str:
        """모델의 문자열 표현을 반환합니다."""
        return f"<BackupStatus(id={self.id}, name='{self.name}', event='{self.event_name}')>"

    @property
    def backup_progress(self) -> dict:
        """
        백업 진행 상태를 딕셔너리로 반환합니다.

        Returns:
            dict: 각 백업 단계의 완료 여부
        """
        return {
            "cam": self.cam or False,
            "master": self.master or False,
            "clean": self.clean or False,
            "final_product": self.final_product or False,
        }

    @property
    def is_fully_backed_up(self) -> bool:
        """
        모든 백업이 완료되었는지 확인합니다.

        Returns:
            bool: 모든 백업 완료 여부
        """
        progress = self.backup_progress
        return all(progress.values())
