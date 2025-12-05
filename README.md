# YM Library Backend

미디어 라이브러리 관리를 위한 FastAPI 백엔드 서버입니다.

## 기능

- **저장소 카탈로그 관리**: 미디어 파일의 저장 위치와 활동 분류 관리
- **백업 상태 추적**: 미디어 파일의 백업 진행 상태 추적

## 기술 스택

- **Framework**: FastAPI 0.104.1
- **Database**: MySQL (SQLAlchemy ORM)
- **Python**: 3.10+

## 프로젝트 구조

```
ym-library-back/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI 앱 진입점
│   ├── config.py         # 환경 설정
│   ├── database.py       # DB 연결 설정
│   ├── models/           # SQLAlchemy 모델
│   │   ├── storage_catalog.py
│   │   └── backup_status.py
│   ├── schemas/          # Pydantic 스키마
│   │   ├── storage_catalog.py
│   │   └── backup_status.py
│   └── routers/          # API 라우터
│       ├── storage_catalog.py
│       └── backup_status.py
├── requirements.txt
├── .gitignore
└── README.md
```

## 설치 및 실행

### 1. 가상환경 생성

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
.\venv\Scripts\activate  # Windows
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```env
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/ym_library
APP_ENV=development
DEBUG=True
```

### 4. 데이터베이스 생성

MySQL에서 데이터베이스를 생성합니다:

```sql
CREATE DATABASE ym_library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. 서버 실행

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API 문서

서버 실행 후 아래 URL에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API 엔드포인트

### 저장소 카탈로그 (`/api/v1/storage-catalogs`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/` | 카탈로그 목록 조회 |
| GET | `/{id}` | 카탈로그 상세 조회 |
| POST | `/` | 카탈로그 생성 |
| PUT | `/{id}` | 카탈로그 수정 |
| DELETE | `/{id}` | 카탈로그 삭제 |

### 백업 상태 (`/api/v1/backup-status`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/` | 백업 상태 목록 조회 |
| GET | `/{id}` | 백업 상태 상세 조회 |
| GET | `/{id}/progress` | 백업 진행 상태 조회 |
| POST | `/` | 백업 상태 생성 |
| PUT | `/{id}` | 백업 상태 수정 |
| PATCH | `/{id}/mark-complete` | 백업 완료 표시 |
| DELETE | `/{id}` | 백업 상태 삭제 |

## 개발

### 테스트 실행

```bash
pytest
```

### 코드 포맷팅

```bash
# black 설치
pip install black

# 코드 포맷팅
black app/
```

## 라이선스

MIT License

