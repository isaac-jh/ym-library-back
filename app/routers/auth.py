"""
인증 및 사용자 API 라우터

로그인 및 사용자 조회 엔드포인트를 제공합니다.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.user import LoginRequest, UserResponse

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    responses={401: {"description": "Unauthorized"}},
)


@router.post("/login", response_model=UserResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    사용자 로그인

    닉네임과 비밀번호를 확인하여 로그인합니다.
    성공 시 사용자 정보를 반환합니다. (비밀번호 제외)

    - **nickname**: 사용자 닉네임
    - **password**: 사용자 비밀번호
    """
    # 닉네임으로 사용자 조회
    user = (
        db.query(User)
        .filter(User.nickname == login_data.nickname, User.deleted == False)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다.",
        )

    # 비밀번호 확인 (단순 비교)
    if user.password != login_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="닉네임 또는 비밀번호가 올바르지 않습니다.",
        )

    return user


@router.get("/users", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    """
    모든 사용자 목록 조회

    삭제되지 않은 모든 사용자 정보를 반환합니다. (비밀번호 제외)
    """
    users = db.query(User).filter(User.deleted == False).all()
    return users
