"""
백업 상태 스키마

API 요청/응답을 위한 Pydantic 스키마 정의
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BackupStatusBase(BaseModel):
    """
    백업 상태 기본 스키마

    공통 필드를 정의합니다.
    """

    event_name: Optional[str] = Field(None, max_length=100, description="이벤트명")
    displayed_date: Optional[datetime] = Field(None, description="표시 날짜")
    name: str = Field(..., max_length=100, description="콘텐츠/파일 이름")
    description: Optional[str] = Field(None, max_length=1000, description="상세 설명")
    cam: Optional[bool] = Field(None, description="카메라 원본 백업 여부")
    cam_checker: Optional[int] = Field(None, description="카메라 원본 확인자 ID")
    master: Optional[bool] = Field(None, description="마스터 파일 백업 여부")
    master_checker: Optional[int] = Field(None, description="마스터 파일 확인자 ID")
    clean: Optional[bool] = Field(None, description="정리본 백업 여부")
    clean_checker: Optional[int] = Field(None, description="정리본 확인자 ID")
    final_product: Optional[bool] = Field(None, description="최종 산출물 백업 여부")
    final_product_checker: Optional[int] = Field(
        None, description="최종 산출물 확인자 ID"
    )


class BackupStatusCreate(BackupStatusBase):
    """
    백업 상태 생성 스키마

    새로운 백업 상태 항목 생성 시 사용됩니다.
    """

    user_ids: Optional[List[int]] = Field(
        None, description="작업자 user_id 리스트 (producers)"
    )
    created_by: int = Field(..., description="생성자 ID (작업자 매핑에 사용)")


class BackupStatusUpdate(BaseModel):
    """
    백업 상태 수정 스키마

    기존 백업 상태 항목 수정 시 사용됩니다.
    모든 필드가 선택적입니다.
    """

    event_name: Optional[str] = Field(None, max_length=100, description="이벤트명")
    displayed_date: Optional[datetime] = Field(None, description="표시 날짜")
    name: Optional[str] = Field(None, max_length=100, description="콘텐츠/파일 이름")
    description: Optional[str] = Field(None, max_length=1000, description="상세 설명")
    cam: Optional[bool] = Field(None, description="카메라 원본 백업 여부")
    cam_checker: Optional[int] = Field(None, description="카메라 원본 확인자 ID")
    master: Optional[bool] = Field(None, description="마스터 파일 백업 여부")
    master_checker: Optional[int] = Field(None, description="마스터 파일 확인자 ID")
    clean: Optional[bool] = Field(None, description="정리본 백업 여부")
    clean_checker: Optional[int] = Field(None, description="정리본 확인자 ID")
    final_product: Optional[bool] = Field(None, description="최종 산출물 백업 여부")
    final_product_checker: Optional[int] = Field(
        None, description="최종 산출물 확인자 ID"
    )
    user_ids: Optional[List[int]] = Field(
        None, description="작업자 user_id 리스트 (producers)"
    )
    updated_by: Optional[int] = Field(
        None, description="수정자 ID (작업자 매핑 변경 시 사용)"
    )


class BackupStatusResponse(BackupStatusBase):
    """
    백업 상태 응답 스키마

    API 응답에 사용됩니다.
    """

    id: int = Field(..., description="고유 식별자")
    created_at: datetime = Field(..., description="생성 일시")

    class Config:
        """Pydantic 설정"""

        from_attributes = True


class BackupStatusListResponse(BaseModel):
    """
    백업 상태 목록 응답 스키마

    목록 조회 시 확인자 이름을 포함하여 반환합니다.
    """

    id: int = Field(..., description="고유 식별자")
    event_name: Optional[str] = Field(None, description="이벤트명")
    displayed_date: Optional[datetime] = Field(None, description="표시 날짜")
    name: str = Field(..., description="콘텐츠/파일 이름")
    description: Optional[str] = Field(None, description="상세 설명")
    cam: Optional[bool] = Field(None, description="카메라 원본 백업 여부")
    cam_checker: Optional[int] = Field(None, description="카메라 원본 확인자 ID")
    cam_checker_name: Optional[str] = Field(None, description="카메라 원본 확인자 이름")
    master: Optional[bool] = Field(None, description="마스터 파일 백업 여부")
    master_checker: Optional[int] = Field(None, description="마스터 파일 확인자 ID")
    master_checker_name: Optional[str] = Field(
        None, description="마스터 파일 확인자 이름"
    )
    clean: Optional[bool] = Field(None, description="정리본 백업 여부")
    clean_checker: Optional[int] = Field(None, description="정리본 확인자 ID")
    clean_checker_name: Optional[str] = Field(None, description="정리본 확인자 이름")
    final_product: Optional[bool] = Field(None, description="최종 산출물 백업 여부")
    final_product_checker: Optional[int] = Field(
        None, description="최종 산출물 확인자 ID"
    )
    final_product_checker_name: Optional[str] = Field(
        None, description="최종 산출물 확인자 이름"
    )
    created_at: datetime = Field(..., description="생성 일시")
    producers: List[str] = Field(default_factory=list, description="작업자 이름 리스트")
