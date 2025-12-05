"""
저장소 카탈로그 모델

활동(Activity) 기반의 저장소 카탈로그 정보를 관리합니다.
영상/이미지 등의 저장 위치와 분류를 추적합니다.
"""

from sqlalchemy import Column, Integer, String

from database import Base


class StorageCatalog(Base):
    """
    저장소 카탈로그 테이블 모델

    미디어 파일의 저장 위치와 활동 분류를 관리하는 테이블입니다.

    Attributes:
        id: 고유 식별자 (자동 증가)
        storage: 저장소 이름/위치 (예: 'NAS1', 'CLOUD')
        category: 카테고리 분류 (기본값: 'ACTIVITY')
        year: 연도
        month: 월
        activity_name: 활동명
        description: 설명
    """

    __tablename__ = "storage_catalog"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="고유 식별자")
    storage = Column(String(20), nullable=False, comment="저장소 이름/위치")
    category = Column(
        String(20), nullable=False, default="ACTIVITY", comment="카테고리 분류"
    )
    year = Column(Integer, nullable=True, comment="연도")
    month = Column(Integer, nullable=True, comment="월")
    activity_name = Column(String(250), nullable=False, comment="활동명")
    description = Column(String(500), nullable=True, comment="설명")

    def __repr__(self) -> str:
        """모델의 문자열 표현을 반환합니다."""
        return (
            f"<StorageCatalog(id={self.id}, storage='{self.storage}', "
            f"activity_name='{self.activity_name}')>"
        )
