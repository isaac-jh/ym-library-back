# YM Library MCP 서버

영상 백업 카탈로그를 자연어로 검색할 수 있게 해주는 MCP 서버 + 챗봇 API.
요구사항/설계 상세는 [`PRD.md`](./PRD.md) 참고.

## 핵심 기능

| # | 기능 | 사용 도구 |
|---|---|---|
| 1 | **영상 백업 위치 찾기** ("가초예 영상 어디 있어?") | `find_video_backup_location` |
| 2 | **장면/소스 검색** ("손을 들고 찬양하는 컷이 필요해") | `search_by_description` |
| 3 | 보조: 저장소 목록 / 최근 활동 | `list_storages`, `list_recent_activities` |

LLM 은 **Google AI Studio - Gemma 4 31B** (`gemma-4-31b-it`) 의
native function calling 을 사용한다.

## 디렉터리

```
mcp/
├── PRD.md                 # 요구사항 정의서 (v1.0.0)
├── README.md              # 본 문서
├── requirements.txt
├── .env.example           # 환경변수 템플릿
├── config.py              # Pydantic Settings
├── db.py                  # SQLAlchemy 세션 + 읽기 전용 ORM
├── tools.py               # 검색 비즈니스 로직
├── llm.py                 # google-genai (Gemma 4) 래퍼
├── mcp_server.py          # FastMCP stdio 진입점
├── chat_app.py            # FastAPI 챗봇 HTTP 앱
└── tests/                 # pytest 단위 테스트
```

## 설치

```bash
# 1) 가상환경 활성화 (프로젝트 루트의 ym-library-back venv 재사용 가능)
source ../ym-library-back/bin/activate

# 2) 의존성 설치
pip install -r requirements.txt

# 3) 환경변수 설정
cp .env.example .env
# .env 를 열어 GOOGLE_API_KEY 등을 채워 넣는다.
```

## 실행

### 1. MCP stdio 서버 (Claude Desktop, Cursor 등)

```bash
PYTHONPATH=. python mcp_server.py
```

Claude Desktop 의 `claude_desktop_config.json` 예시:

```jsonc
{
  "mcpServers": {
    "ym-library": {
      "command": "/abs/path/to/ym-library-back/ym-library-back/bin/python",
      "args": ["/abs/path/to/ym-library-back/mcp/mcp_server.py"],
      "env": {
        "DATABASE_URL": "mysql+pymysql://user:pw@host:3306/ym",
        "PYTHONPATH": "/abs/path/to/ym-library-back/mcp"
      }
    }
  }
}
```

### 2. 카탈로그 페이지용 HTTP 챗봇

```bash
PYTHONPATH=. python chat_app.py
# → http://0.0.0.0:8001
```

#### `POST /chat`

```bash
curl -X POST http://localhost:8001/chat \
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

#### 프론트엔드 연동 가이드

1. 카탈로그 페이지에서 챗봇 위젯을 만들고, 이전 대화를 `history` 배열로
   누적해 함께 전송한다.
2. `tool_calls` 는 디버깅/감사용으로만 노출하고, 실제 사용자에게는
   `reply` 만 보여주면 된다.
3. CORS 는 운영에서 `CHAT_CORS_ORIGINS=https://your-frontend.com` 처럼
   화이트리스트로 제한할 것 (PRD §6, TODO).

## 테스트

```bash
PYTHONPATH=. pytest -v
```

테스트는 인메모리 SQLite 와 LLM mock 으로 동작하므로 외부 API 키 없이
실행 가능하다.

## 환경변수

| Key | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `mysql+pymysql://root:password@localhost:3306/ym` | MySQL DSN |
| `GOOGLE_API_KEY` | (필수) | https://aistudio.google.com/apikey |
| `GEMMA_MODEL` | `gemma-4-31b-it` | Google AI Studio 모델 ID |
| `MCP_SERVER_NAME` | `ym-library-mcp` | MCP 서버 표시 이름 |
| `CHAT_API_HOST` | `0.0.0.0` | FastAPI 호스트 |
| `CHAT_API_PORT` | `8001` | FastAPI 포트 |
| `CHAT_CORS_ORIGINS` | `*` | CSV. 운영에서는 화이트리스트 권장 |

## 향후 과제

PRD §9 참고. 임베딩 시맨틱 검색, 응답 캐싱, 인증, SSE 스트리밍, MCP HTTP
트랜스포트 등이 v1.1+ 로 예정되어 있다.
