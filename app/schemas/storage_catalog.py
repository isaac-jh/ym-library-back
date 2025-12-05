"""
저장소 카탈로그 스키마

API 요청/응답을 위한 Pydantic 스키마 정의
"""

from typing import Optional

from pydantic import BaseModel, Field


class StorageCatalogBase(BaseModel):
    """
    저장소 카탈로그 기본 스키마

    공통 필드를 정의합니다.
    """

    storage: str = Field(..., max_length=20, description="저장소 이름/위치")
    category: str = Field(
        default="ACTIVITY", max_length=20, description="카테고리 분류"
    )
    year: Optional[int] = Field(None, ge=1900, le=2100, description="연도")
    month: Optional[int] = Field(None, ge=1, le=12, description="월")
    activity_name: str = Field(..., max_length=250, description="활동명")
    description: Optional[str] = Field(None, max_length=500, description="설명")


class StorageCatalogCreate(StorageCatalogBase):
    """
    저장소 카탈로그 생성 스키마

    새로운 카탈로그 항목 생성 시 사용됩니다.
    """

    pass


class StorageCatalogUpdate(BaseModel):
    """
    저장소 카탈로그 수정 스키마

    기존 카탈로그 항목 수정 시 사용됩니다.
    모든 필드가 선택적입니다.
    """

    storage: Optional[str] = Field(None, max_length=20, description="저장소 이름/위치")
    category: Optional[str] = Field(None, max_length=20, description="카테고리 분류")
    year: Optional[int] = Field(None, ge=1900, le=2100, description="연도")
    month: Optional[int] = Field(None, ge=1, le=12, description="월")
    activity_name: Optional[str] = Field(None, max_length=250, description="활동명")
    description: Optional[str] = Field(None, max_length=500, description="설명")


class StorageCatalogResponse(StorageCatalogBase):
    """
    저장소 카탈로그 응답 스키마

    API 응답에 사용됩니다.
    """

    id: int = Field(..., description="고유 식별자")

    class Config:
        """Pydantic 설정"""

        from_attributes = True

