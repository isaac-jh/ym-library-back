"""
사용자 스키마

API 요청/응답을 위한 Pydantic 스키마 정의
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """
    사용자 기본 스키마

    공통 필드를 정의합니다.
    """

    name: str = Field(..., max_length=10, description="사용자 이름")
    nickname: str = Field(..., max_length=200, description="닉네임")


class UserResponse(UserBase):
    """
    사용자 응답 스키마

    API 응답에 사용됩니다.
    비밀번호는 응답에 포함되지 않습니다.
    """

    id: int = Field(..., description="고유 식별자")
    deleted: bool = Field(..., description="삭제 여부")
    created_at: datetime = Field(..., description="생성 일시")

    model_config = ConfigDict(from_attributes=True)


class UserSimpleResponse(BaseModel):
    """
    사용자 간단 응답 스키마

    목록 조회 등에서 간단한 정보만 반환할 때 사용됩니다.
    """

    id: int = Field(..., description="고유 식별자")
    name: str = Field(..., description="사용자 이름")

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """
    로그인 요청 스키마

    로그인 시 닉네임과 비밀번호를 받습니다.
    """

    nickname: str = Field(..., max_length=200, description="닉네임")
    password: str = Field(..., description="비밀번호")
