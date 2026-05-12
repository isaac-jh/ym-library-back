# 카탈로그 챗봇 & MCP 서버

YM Library 백엔드에 통합된 **카탈로그 챗봇 + MCP 서버** 가이드.

- **버전**: v1.1.1 (2026-05-11) — 챗봇/MCP 검색 도구는 `storage_catalog` 만 조회
- **이전 분리 버전(v1.0.0)** PRD 는 git history 의 `mcp/PRD.md` 에서 확인 가능

---

## 1. 개요

YM Library 의 백업 카탈로그(영상/콘텐츠 보관 위치) 데이터를 자연어로
조회하기 위한 챗봇 + MCP 서버. 두 가지 형태로 사용된다.

1. **HTTP 챗봇 엔드포인트** (`POST /api/v1/chat`)
   카탈로그 페이지에 임베드되는 챗봇이 호출하는 REST API. 기존 `app/`
   FastAPI 서버에 통합되어 있으므로 **별도 배포 불필요**.

2. **표준 MCP stdio 서버** (`app/mcp_server.py`)
   Claude Desktop / Cursor / Continue 등 외부 MCP 클라이언트에서 직접
   도구로 사용. 같은 비즈니스 로직(`services.catalog_search`)을 공유한다.

LLM 은 Google AI Studio - **Gemma 4 31B** (`gemma-4-31b-it`) 의
native function calling 을 사용한다.

## 2. 핵심 기능

| # | 기능 | 사용 도구 | 예시 |
|---|---|---|---|
| 1 | **영상 백업 위치 찾기** | `find_video_backup_location` | "가초예 영상 어디 있어?" |
| 2 | **장면/소스 검색** | `search_by_description` | "손을 들고 찬양하는 컷이 필요해" |
| 3 | 보조: 저장소 목록 | `list_storages` | "어떤 저장소가 있어?" |
| 4 | 보조: 최근 활동 | `list_recent_activities` | (LLM 컨텍스트용) |

## 3. 아키텍처

```
프론트 카탈로그 챗봇
    │  POST /api/v1/chat
    ▼
app/routers/chat.py
    │
    ▼
app/services/llm.py  ──────────────► Gemma 4 31B (Google AI Studio)
    │   automatic_function_calling     │
    │                                  │  function call
    │   ◄──────────────────────────────┘
    ▼
app/services/catalog_search.py
    │  session_scope() → SessionLocal()
    ▼
app/models/StorageCatalog   (챗/MCP 도구는 이 테이블만 조회)
    │
    ▼
MySQL  (``backup_status`` 는 REST 백업 API 전용, 챗 도구와 무관)

# 별도 entrypoint
Claude Desktop / Cursor
    │  stdio (별도 프로세스)
    ▼
app/mcp_server.py  ─► services.catalog_search.* (같은 함수 재사용)
```

## 4. 디렉터리 구조 (관련 부분만)

```
app/
├── main.py                          # chat 라우터 등록
├── config.py                        # google_api_key, gemma_model
├── database.py                      # session_scope contextmanager 추가
├── mcp_server.py                    # FastMCP stdio entrypoint
├── models/
│   ├── storage_catalog.py
│   └── backup_status.py
├── schemas/
│   └── chat.py                      # ChatRequest, ChatResponse, ToolCallRecord
├── routers/
│   └── chat.py                      # POST /chat, GET /chat/health
└── services/                        # 신규 패키지
    ├── catalog_search.py            # 검색 도구 함수 + TOOL_FUNCTIONS
    └── llm.py                       # Gemma 4 래퍼

tests/
├── conftest.py                      # 인메모리 SQLite 시드
├── test_catalog_search.py
└── test_chat_router.py

docs/
└── mcp.md                           # 본 문서
```

## 5. 환경변수

루트 `.env.example` 참고. 새로 추가된 키만 정리:

| Key | 기본값 | 설명 |
|---|---|---|
| `GOOGLE_API_KEY` | (필수) | https://aistudio.google.com/apikey |
| `GEMMA_MODEL` | `gemma-4-31b-it` | Google AI Studio 모델 ID |
| `MCP_SERVER_NAME` | `ym-library-mcp` | MCP stdio 서버 표시 이름 |

## 6. 실행

### 6.1. HTTP 챗봇 (FastAPI 서버에 포함)

```bash
# 평소처럼 백엔드 서버를 띄우면 챗봇 라우터도 자동 활성화된다.
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 헬스 체크
curl http://localhost:8000/api/v1/chat/health
# {"status":"ok","model":"gemma-4-31b-it"}

# 챗
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "가초예 영상 어디 백업되어 있어?",
    "history": []
  }'
```

응답 예시:

```jsonc
{
  "reply": "'가족초청예배(가초예)' 영상은 다음과 같이 백업되어 있습니다.\n• 2024년: NAS-A\n• 2025년: NAS-B",
  "tool_calls": [
    { "name": "find_video_backup_location", "args": { "keyword": "가초예" } }
  ]
}
```

### 6.2. MCP stdio 서버 (Claude Desktop / Cursor 등)

`claude_desktop_config.json` 예시:

```jsonc
{
  "mcpServers": {
    "ym-library": {
      "command": "/abs/path/to/ym-library-back/ym-library-back/bin/python",
      "args": ["/abs/path/to/ym-library-back/app/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/abs/path/to/ym-library-back/app",
        "DATABASE_URL": "mysql+pymysql://user:pw@host:3306/ym",
        "GOOGLE_API_KEY": "...",
        "GEMMA_MODEL": "gemma-4-31b-it"
      }
    }
  }
}
```

> stdio 트랜스포트는 stdout 을 프로토콜 채널로 점유한다. 모든 로그는
> stderr 로 출력하도록 구성되어 있다.

### 6.3. 프론트엔드 연동 가이드

1. 카탈로그 페이지에서 챗봇 위젯을 만들고, 이전 대화를 `history` 배열로
   누적해 함께 전송한다.
2. `tool_calls` 는 디버깅/감사용으로만 노출하고, 실제 사용자에게는
   `reply` 만 보여주면 된다.
3. CORS 는 기존 `app/main.py` 의 정책을 그대로 따른다(현재 `*` 허용,
   운영에서는 화이트리스트로 제한 필요 — 기존 TODO).

## 7. 도커

기존 `Dockerfile` 만 사용하면 챗봇 라우터까지 함께 포함된다. **별도
이미지/컨테이너 빌드 불필요**. 환경변수만 채워주면 끝.

```bash
docker compose up -d --build
```

`docker-compose.yml` 의 `environment` 에 다음만 추가하면 된다.

```yaml
environment:
  - DATABASE_URL=...
  - GOOGLE_API_KEY=...
  - GEMMA_MODEL=gemma-4-31b-it
```

MCP stdio 서버를 도커로 띄우고 싶을 때:

```bash
docker exec -i <api-container> python /app/mcp_server.py
```

## 8. 테스트

```bash
PYTHONPATH=app pytest -v
```

테스트는 인메모리 SQLite 와 LLM mock 으로 동작하므로 외부 API 키 없이
실행 가능하다.

## 9. 향후 과제 (TODO)

- [ ] **임베딩 기반 시맨틱 검색** (description 벡터화 → pgvector / FAISS)
- [ ] **응답 캐싱** (동일 질의 LLM 호출 절감)
- [ ] **인증/권한** (JWT 토큰 검증, 부서별 권한)
- [ ] **스트리밍 응답** (SSE)
- [ ] **사용 로그 수집 → 검색 품질 분석**
- [ ] **다국어 지원** (영문 질의 처리)
- [ ] **MCP HTTP/SSE transport** 추가 (현재는 stdio만)
- [ ] 챗봇 트래픽이 헤비해지면 **services.* 만 별도 마이크로서비스로 분리**

## 10. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v1.0.0 | 2026-05-11 | 분리된 `mcp/` 디렉터리로 최초 구현 |
| v1.1.0 | 2026-05-11 | `app/` 에 흡수 — 단일 서버 / 단일 도커 이미지로 통합 |
