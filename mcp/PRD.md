# YM Library MCP 서버 PRD

- **버전**: v1.0.0
- **작성일**: 2026-05-11
- **작성자**: backend team
- **대상 모듈**: `mcp/`

---

## 1. 개요

YM Library 프로젝트의 백업 카탈로그(영상/콘텐츠 보관 위치) 데이터를 자연어로
조회할 수 있게 해주는 **MCP(Model Context Protocol) 서버**를 구축한다.
이 서버는 두 가지 형태로 사용된다.

1. **표준 MCP stdio 서버**
   Claude Desktop, Cursor 등 외부 MCP 클라이언트에서 직접 도구로 사용.
2. **HTTP 챗봇 엔드포인트**
   프론트엔드 **카탈로그 페이지**에 임베드되는 챗봇이 호출하는 REST API.
   내부적으로 동일한 도구를 Google AI Studio의 **Gemma 4 31B**가 호출.

## 2. 배경 및 목표

기존에는 영상이 어느 NAS/HDD에 보관되어 있는지, 특정 장면이 들어있는 영상이
무엇인지를 사람이 카탈로그 표를 직접 검색해 찾아야 했다.
챗봇으로 다음 두 질문을 자연어로 즉시 해결할 수 있게 한다.

| # | 핵심 시나리오 | 예시 입력 | 기대 동작 |
|---|---|---|---|
| 1 | **영상 백업 위치 찾기** | "가족초청예배(가초예) 영상 어디 있어?" | `storage_catalog`에서 활동명/연도별 매칭 → 위치(storage)를 연도별로 묶어 답변 |
| 2 | **장면/소스 검색** | "손을 들고 찬양하고 있는 그림이 필요해" | `backup_status.description` + `storage_catalog.description`을 키워드 검색 → 가장 관련성 높은 항목과 그 백업 위치를 답변 |

## 3. 비-목표 (Out of Scope)

- 영상 파일 자체의 미리보기/재생
- 카탈로그 데이터의 **수정/삭제** (읽기 전용 챗봇)
- 사용자 인증/권한 (1.0에서는 내부망 사용 가정, TODO로 남김)
- 의미(임베딩) 기반 시맨틱 검색 — v1.1에서 도입 검토

## 4. 사용자 시나리오

### 4.1. 영상 위치 찾기
```
User : 가초예 영상 어디 백업되어 있어?
Bot  : '가족초청예배(가초예)' 관련 영상은 다음과 같이 백업되어 있습니다.
       • 2024년: NAS-A (ACTIVITY/가족초청예배)
       • 2025년: NAS-B (ACTIVITY/가족초청예배 - 봄)
```

### 4.2. 장면/소스 검색
```
User : 손을 들고 찬양하는 컷이 들어있는 영상 있어?
Bot  : description 검색 결과,
       • 'YM 컨퍼런스 2024 셋째날 통성기도' (NAS-A) — 모든 회중이 손을 들고 찬양하는 장면 포함
       • '청년부 임직예배 영상 1차 편집본' (CLOUD) — 후반부 손 든 회중 컷
       두 영상이 가장 적합합니다.
```

## 5. 기능 요구사항

### 5.1. MCP Tool 정의

| 이름 | 설명 | 주요 파라미터 |
|---|---|---|
| `find_video_backup_location` | 활동명/연도/카테고리 기준 백업 위치 조회 | `keyword: str`, `year?: int`, `category?: str`, `limit?: int` |
| `search_by_description` | description 컬럼(카탈로그+백업)에서 키워드 검색 | `keyword: str`, `limit?: int` |
| `list_storages` | 등록된 모든 저장소 목록 | `(none)` |
| `list_recent_activities` | 최근 등록된 활동 목록 (LLM이 컨텍스트 파악용) | `limit?: int` |

> 도구 이름은 `mcp_best_practices`에 따라 `snake_case`로 통일.

### 5.2. HTTP 챗봇 엔드포인트

`POST /chat`

```jsonc
// Request
{
  "message": "가초예 영상 어디 있어?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "model", "content": "..." }
  ]
}

// Response
{
  "reply": "...",
  "tool_calls": [
    { "name": "find_video_backup_location", "args": { "keyword": "가초예" } }
  ]
}
```

`GET /health` — 헬스체크.

### 5.3. LLM

- 모델: `gemma-4-31b-it` (Google AI Studio, native function calling 지원)
- SDK: `google-genai >= 1.70`
- 시스템 프롬프트: 한국어 응답, 영상/장면 검색 도우미 페르소나 부여
- 자동 함수 호출(automatic function calling) 활성

## 6. 비기능 요구사항

| 항목 | 요구 |
|---|---|
| 언어 | Python 3.10+ |
| 코드 스타일 | PEP 8 + Google docstring |
| 환경변수 | `mcp/.env` 로 분리 (`.gitignore`에 자동 포함) |
| 응답 시간 | 단일 도구 호출 1.5s 이내(DB만), 챗 전체 5s 이내 목표 |
| 로그 | MCP stdio 서버는 stderr 로깅 필수 (프로토콜 무결성) |

## 7. 디렉터리 구조

```
mcp/
├── PRD.md                 # 본 문서
├── README.md              # 사용/배포 가이드
├── requirements.txt
├── .env.example
├── .env                   # (gitignore)
├── config.py              # Pydantic Settings
├── db.py                  # SQLAlchemy 세션 + 최소 ORM 모델
├── tools.py               # 검색 비즈니스 로직 (DB 호출)
├── llm.py                 # google-genai 래퍼
├── mcp_server.py          # FastMCP stdio 진입점
├── chat_app.py            # FastAPI HTTP 챗봇 앱
├── run_chat.py            # uvicorn 실행 헬퍼
└── tests/
    ├── __init__.py
    ├── test_tools.py
    └── test_chat_app.py
```

## 8. 환경변수

| Key | 용도 | 예시 |
|---|---|---|
| `DATABASE_URL` | MySQL 연결 문자열 | `mysql+pymysql://user:pw@host:3306/ym` |
| `GOOGLE_API_KEY` | Google AI Studio API 키 | `AIza...` |
| `GEMMA_MODEL` | 사용할 Gemma 모델 ID | `gemma-4-31b-it` |
| `MCP_SERVER_NAME` | MCP 서버 이름 | `ym-library-mcp` |
| `CHAT_API_HOST` | 챗 API 바인딩 호스트 | `0.0.0.0` |
| `CHAT_API_PORT` | 챗 API 바인딩 포트 | `8001` |
| `CHAT_CORS_ORIGINS` | 허용 Origin (CSV) | `*` (TODO: 운영에선 화이트리스트) |

## 9. 향후 과제 (TODO)

- [ ] **임베딩 기반 시맨틱 검색** (description 벡터화 → pgvector/Milvus/FAISS)
- [ ] **응답 캐싱** (동일 질의 LLM 호출 절감)
- [ ] **인증/권한** (JWT 토큰 검증, 부서별 권한)
- [ ] **스트리밍 응답** (SSE)
- [ ] **사용 로그 수집 → 검색 품질 분석**
- [ ] **다국어 지원** (영문 질의 처리)
- [ ] **MCP HTTP/SSE transport** 추가 (현재는 stdio만)

## 10. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v1.0.0 | 2026-05-11 | 최초 작성 — MCP 서버 + 챗봇 HTTP 엔드포인트 |
