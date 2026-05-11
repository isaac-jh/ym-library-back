"""
YM Library Backend - 메인 애플리케이션

FastAPI 애플리케이션의 진입점입니다.
라우터 등록 및 미들웨어 설정을 담당합니다.
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import get_settings
from database import engine

# 모든 모델을 import하여 SQLAlchemy가 관계를 인식하도록 함
# 순서 중요: User -> BackupStatus -> MUserBackupStatus
import models  # noqa: F401

from routers import auth, backup_status, chat, storage_catalog

# 설정 로드
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 라이프사이클 관리

    서버 시작 시 데이터베이스 연결을 확인합니다.
    """
    # 시작 시 실행
    print("🚀 서버 시작 중...")

    # 데이터베이스 연결 체크
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ 데이터베이스 연결 성공")
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        raise e

    print("✅ 서버 시작 완료")

    yield  # 서버 실행 중

    # 종료 시 실행
    print("👋 서버 종료 중...")
    engine.dispose()
    print("✅ 서버 종료 완료")


# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="YM Library API",
    description="미디어 라이브러리 관리를 위한 백엔드 API 서버",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    # trailing slash로 인한 307 리다이렉트 방지
    redirect_slashes=False,
)

# CORS 미들웨어 설정
#
# 주의: starlette 0.41+ 부터 `allow_origins=["*"]` 와 `allow_credentials=True`
# 조합이 명세에 맞게 거부된다. 그 결과 응답에 `Access-Control-Allow-Origin`
# 헤더가 누락되어 브라우저가 차단한다. 운영/개발 모두 **명시 도메인**을
# 환경변수(CORS_ALLOWED_ORIGINS) 로 나열한다.
#
# preview 배포(예: vercel) 처럼 와일드카드가 필요하면
# CORS_ALLOWED_ORIGIN_REGEX 에 정규식을 지정한다.
_cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
    "allow_origins": settings.cors_origin_list,
}
if settings.cors_allowed_origin_regex:
    _cors_kwargs["allow_origin_regex"] = settings.cors_allowed_origin_regex

app.add_middleware(CORSMiddleware, **_cors_kwargs)

# 라우터 등록
app.include_router(auth.router, prefix="/api/v1")
app.include_router(storage_catalog.router, prefix="/api/v1")
app.include_router(backup_status.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


@app.get("/")
async def root():
    """
    루트 엔드포인트

    API 서버 상태를 확인합니다.
    """
    return {
        "message": "YM Library API 서버가 정상 작동 중입니다.",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """
    헬스 체크 엔드포인트

    서버 상태 확인을 위한 간단한 엔드포인트입니다.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    """
    서버 직접 실행

    python main.py 명령으로 서버를 실행할 수 있습니다.
    개발 환경에서는 --reload 옵션이 활성화됩니다.
    """
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        proxy_headers=True,  # 프록시 헤더 인식 (X-Forwarded-Proto 등)
        forwarded_allow_ips="*",  # 모든 프록시 IP 허용
    )
