---
title: 카탈로그 챗봇 — 프론트엔드 통합 가이드
audience: AI coding agent (Cursor / Copilot 등) + 프론트엔드 개발자
backend_version: v1.1.0
last_updated: 2026-05-11
purpose: |
  YM Library 카탈로그 페이지의 챗봇 위젯을 구현하는 데 필요한 모든 정보를
  단일 파일로 제공한다. 이 문서만 읽고 그대로 따라 구현해도 동작해야 한다.
---

# 카탈로그 챗봇 — 프론트엔드 통합 가이드

## 0. TL;DR

```ts
// 한 번의 챗 호출
const res = await fetch(`${API_BASE}/api/v1/chat`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: userInput,        // string, 1자 이상
    history: prevTurns,        // [{role: "user"|"model", content: string}, ...]
  }),
});
const { reply, tool_calls } = await res.json();
// → reply 만 화면에 출력, tool_calls 는 디버깅용
```

- Base URL: 백엔드 FastAPI 서버 주소 (예: `http://localhost:8000`)
- 인증: **현재 없음** (PRD §9 TODO). CORS 는 백엔드 측 `*` 허용
- 응답: 항상 한국어 (백엔드 system prompt 고정)
- 모델: Google AI Studio `gemma-4-31b-it` (변경 가능)

---

## 1. 엔드포인트 사양

### 1.1. `POST /api/v1/chat`

챗봇 한 턴을 처리한다. 내부에서 LLM 이 자동으로 검색 도구를 호출하고
한국어 자연어 답변을 생성한다.

#### Request

```http
POST /api/v1/chat HTTP/1.1
Content-Type: application/json
```

```ts
interface ChatRequest {
  /** 사용자 입력 메시지. 1자 이상. 빈 문자열은 422. */
  message: string;
  /** 이전 대화 히스토리. 오래된 순(첫 항목이 가장 오래됨). 생략 또는 null/[] 가능. */
  history?: ChatTurn[] | null;
}

interface ChatTurn {
  /** "user" 또는 "model" 두 값만 허용. 다른 값은 백엔드에서 "user" 로 강제 변환됨. */
  role: "user" | "model";
  /** 빈 문자열은 history 변환 단계에서 자동으로 제외됨. */
  content: string;
}
```

#### Response — 200 OK

```ts
interface ChatResponse {
  /** 화면에 표시할 한국어 답변. 항상 비어있지 않음 (모델이 빈 응답일 때도 폴백 문구가 들어감). */
  reply: string;
  /**
   * 답변 생성 과정에서 LLM 이 자동 호출한 검색 도구 목록.
   * 디버깅/감사용. 사용자에게 직접 노출하지 말 것.
   * 호출이 없었다면 빈 배열.
   */
  tool_calls: ToolCallRecord[];
}

interface ToolCallRecord {
  /** "find_video_backup_location" | "search_by_description" | "list_storages" | "list_recent_activities" */
  name: string;
  /** 도구에 전달된 인자. JSON object. 도구별 스키마는 §3 참조. */
  args: Record<string, unknown>;
}
```

#### Response — 에러

| Status | 의미 | 처리 가이드 |
|---|---|---|
| `422 Unprocessable Entity` | `message` 가 빈 문자열 | 입력창에서 미리 trim/min-length 검증 |
| `500 Internal Server Error` | 서버 설정 오류 (예: `GOOGLE_API_KEY` 미설정) | 사용자에게 "일시적 오류" 메시지, Sentry 등으로 알림 |
| `502 Bad Gateway` | LLM 호출 실패 / 네트워크 오류 | 재시도 1~2회 후 "일시적 오류" 메시지 |

에러 응답 바디는 FastAPI 표준 형식.

```jsonc
// 예) 500
{ "detail": "GOOGLE_API_KEY 가 설정되지 않았습니다. .env 를 확인하세요." }
```

### 1.2. `GET /api/v1/chat/health`

챗봇 모듈 헬스 체크. 사용 모델 ID 도 함께 돌려준다.
프론트에서 진단/표시 용도로 옵션.

```ts
interface ChatHealthResponse {
  status: "ok";
  /** 현재 사용 중인 모델 ID. 예: "gemma-4-31b-it" */
  model: string;
}
```

---

## 2. 동작 모델 (LLM 이 어떻게 답하는지)

```
사용자 메시지
  ↓
[Gemma 4 31B + system prompt + tools]
  ↓ (자동 함수 호출, 최대 6회)
검색 도구 1~N 회 호출
  ↓ (도구 결과 누적)
한국어 답변 생성
  ↓
{ reply, tool_calls }
```

핵심 규칙(백엔드 system prompt 발췌. 프론트에서 별도 프롬프트 주입할 필요 없음):

- **답변은 항상 한국어**
- **도구 결과만 근거로 답변**. 결과가 비면 "모른다 + 더 구체적인 키워드 요청"
- 영상 위치 질문 → `find_video_backup_location`
- 장면/소스 질문 → `search_by_description`
- 결과 여러 건 → 연도/저장소별로 묶어 항목 형태
- `storage`, `year`, `activity_name` / `name` 을 답변에 함께 표기

---

## 3. 사용되는 백엔드 도구 (참고용, 직접 호출 불필요)

프론트는 **도구를 직접 호출하지 않는다.** `POST /chat` 한 번이면 충분.
아래 정보는 `tool_calls` 로그를 해석하거나 디버깅 시 참고용.

| name | 용도 | args 키 |
|---|---|---|
| `find_video_backup_location` | 활동명/별칭으로 백업 위치 검색 | `keyword: string`, `year?: number`, `category?: string`, `limit?: number` |
| `search_by_description` | description 키워드로 장면 검색 | `keyword: string`, `limit?: number` |
| `list_storages` | 저장소 목록 | (none) |
| `list_recent_activities` | 최근 활동 목록 | `limit?: number` |

`limit` 기본 20, 최대 50.

---

## 4. 요청/응답 예시 (복사용)

### 4.1. 첫 질문 (history 없음)

#### Request
```json
{
  "message": "가초예 영상 어디 백업되어 있어?"
}
```

#### Response
```json
{
  "reply": "'가족초청예배(가초예)' 영상은 다음과 같이 백업되어 있습니다.\n• 2025년: NAS-B (가족초청예배)\n• 2024년: NAS-A (가족초청예배(가초예))",
  "tool_calls": [
    {
      "name": "find_video_backup_location",
      "args": { "keyword": "가초예" }
    }
  ]
}
```

### 4.2. 후속 질문 (history 누적)

#### Request
```json
{
  "message": "그 중 2024년 영상만 알려줘",
  "history": [
    { "role": "user",  "content": "가초예 영상 어디 백업되어 있어?" },
    { "role": "model", "content": "'가족초청예배(가초예)' 영상은 다음과 같이 백업되어 있습니다.\n• 2025년: NAS-B\n• 2024년: NAS-A" }
  ]
}
```

#### Response
```json
{
  "reply": "2024년 가족초청예배 영상은 NAS-A 에 백업되어 있습니다.",
  "tool_calls": [
    {
      "name": "find_video_backup_location",
      "args": { "keyword": "가족초청예배", "year": 2024 }
    }
  ]
}
```

### 4.3. 장면/소스 검색

#### Request
```json
{ "message": "손을 들고 찬양하는 컷이 들어있는 영상 있어?" }
```

#### Response
```json
{
  "reply": "다음 영상에 해당 장면이 포함되어 있습니다.\n• 청년부 임직예배 (2024-12, CLOUD) — 회중이 손을 들고 찬양하는 장면 다수 포함\n• 임직예배 1차 편집본 (CLOUD) — 후반부 손 든 회중 컷",
  "tool_calls": [
    {
      "name": "search_by_description",
      "args": { "keyword": "손을 들고 찬양" }
    }
  ]
}
```

### 4.4. 결과 없음

#### Request
```json
{ "message": "외계인 등장 영상" }
```

#### Response
```json
{
  "reply": "관련 영상을 찾지 못했습니다. 좀 더 구체적인 키워드(예: 활동명, 장면 묘사)를 알려주실 수 있을까요?",
  "tool_calls": [
    { "name": "search_by_description", "args": { "keyword": "외계인" } }
  ]
}
```

### 4.5. 검증 오류

#### Request
```json
{ "message": "" }
```

#### Response — 422
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "message"],
      "msg": "String should have at least 1 character",
      "input": ""
    }
  ]
}
```

---

## 5. 프론트엔드 구현 패턴

### 5.1. 최소 fetch 클라이언트 (TypeScript)

```ts
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type ChatRole = "user" | "model";
export interface ChatTurn { role: ChatRole; content: string; }
export interface ToolCallRecord { name: string; args: Record<string, unknown>; }
export interface ChatResponse { reply: string; tool_calls: ToolCallRecord[]; }

export async function sendChat(
  message: string,
  history: ChatTurn[] = [],
  signal?: AbortSignal
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new ChatApiError(res.status, detail);
  }
  return res.json() as Promise<ChatResponse>;
}

export class ChatApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`Chat API ${status}: ${detail}`);
  }
}
```

### 5.2. React 훅 (히스토리 자동 누적)

```tsx
import { useCallback, useState } from "react";

interface UseCatalogChatResult {
  history: ChatTurn[];
  isLoading: boolean;
  error: string | null;
  send: (message: string) => Promise<void>;
  reset: () => void;
}

export function useCatalogChat(): UseCatalogChatResult {
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = useCallback(async (message: string) => {
    const trimmed = message.trim();
    if (!trimmed || isLoading) return;

    // 낙관적 업데이트: 사용자 메시지 즉시 표시
    const nextHistory: ChatTurn[] = [...history, { role: "user", content: trimmed }];
    setHistory(nextHistory);
    setLoading(true);
    setError(null);

    try {
      // history 는 "현재 사용자 메시지를 제외한 과거 대화"를 보낸다
      const { reply } = await sendChat(trimmed, history);
      setHistory((h) => [...h, { role: "model", content: reply }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "알 수 없는 오류";
      setError(msg);
      // 실패 시 사용자 메시지를 history 에서 제거(선택)
      setHistory((h) => h.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }, [history, isLoading]);

  const reset = useCallback(() => {
    setHistory([]);
    setError(null);
  }, []);

  return { history, isLoading, error, send, reset };
}
```

### 5.3. 메시지 렌더링 규칙

- `reply` 는 **plain text** 다. 백엔드는 마크다운을 보장하지 않지만,
  목록에 `•` / `-` / 줄바꿈을 포함할 수 있다. 줄바꿈은 `white-space: pre-wrap`
  또는 `\n` → `<br/>` 변환으로 처리.
- HTML 인젝션 방지를 위해 **반드시 텍스트 노드로 렌더링** (innerHTML 금지).
- `tool_calls` 는 화면 본문에는 노출하지 않는다. 개발자 도구나 토글
  가능한 디버그 패널에서만.

### 5.4. 권장 입력 UX

- 엔터로 전송, Shift+Enter 로 줄바꿈
- 전송 중에는 입력창 비활성화 + 로딩 인디케이터
- `AbortController` 로 화면 이탈 시 진행 중 요청 취소
- 사용자가 빠르게 여러 번 누르는 것을 막기 위해 **연속 호출 디바운스/락**

---

## 6. 안티패턴 (하지 말 것)

| 하지 말 것 | 이유 / 대안 |
|---|---|
| `tool_calls` 를 답변과 함께 그대로 출력 | 사용자 혼란. 디버그 패널에만 표시. |
| `history` 에 `role: "system"` / `"assistant"` 등을 넣기 | `user` / `model` 이외 값은 백엔드가 `user` 로 강제 변환 → 대화 맥락 손상 |
| 사용자 메시지를 보내기 직전 history 에 추가한 뒤 `history` 인자에 그대로 포함 | 같은 메시지가 두 번 들어가 모델이 혼란. 보내는 시점의 history 는 **이전까지의 대화** 만 포함. |
| `reply` 를 `dangerouslySetInnerHTML` 로 렌더링 | XSS. 텍스트 노드 + `pre-wrap` 사용. |
| 422 응답을 사용자에게 그대로 노출 | "메시지를 입력하세요" 같은 친화적 문구로 대체 |
| `history` 에 수십~수백 턴을 무한 누적 | 토큰/지연 비용 ↑. 최근 N턴(예: 20턴) 또는 N자(예: 4000자)로 자르기 |
| 같은 질문을 반복 호출 | 응답 캐싱이 백엔드에 아직 없음(TODO). 프론트에서 **동일 메시지+history** 키로 단기 캐시 권장 |
| API Base URL 하드코딩 | 환경변수(`VITE_API_BASE_URL` 등)로 분리 |

---

## 7. 운영 환경 체크리스트

| 항목 | 확인 방법 |
|---|---|
| 백엔드 챗봇 활성화 여부 | `GET /api/v1/chat/health` → `{"status":"ok","model":"gemma-4-31b-it"}` |
| 백엔드 자체 헬스 | `GET /health` → `{"status":"healthy"}` |
| CORS 허용 | 백엔드 `.env` 의 `CORS_ALLOWED_ORIGINS` (CSV) 에 프론트 도메인이 포함되어 있어야 함. 와일드카드(`*`) 는 `credentials=True` 와 함께 쓸 수 없으므로 명시 도메인 필요. preview 배포는 `CORS_ALLOWED_ORIGIN_REGEX` 로 매칭 |
| 모델 변경 | 백엔드 `.env` 의 `GEMMA_MODEL` 만 수정. 프론트 코드 변경 불필요 |

---

## 8. 자주 받는 질문 (FAQ)

**Q. 스트리밍 응답(SSE)이 가능한가?**
A. 현재 v1.1.0 에서는 **단발형 응답만** 지원. SSE 는 PRD §9 TODO.

**Q. 한 번에 여러 검색 도구가 호출될 수 있나?**
A. 가능. 백엔드는 자동 함수 호출 최대 6회까지 허용. `tool_calls` 가
2개 이상 들어있을 수 있으므로 배열로 처리.

**Q. 응답 시간은?**
A. 단일 도구 호출 ≤1.5s, 전체 ≤5s 가 목표(PRD §6). 네트워크/모델
부하에 따라 변동. 클라이언트 측 timeout 은 30s 권장.

**Q. 결과가 없을 때는?**
A. `reply` 에 한국어 안내문이 들어오고 `tool_calls` 는 비거나 1개.
프론트에서 별도 분기 불필요.

**Q. 인증이 필요한가?**
A. v1.1.0 에서는 **없음**. 운영 배포 시 JWT 추가 예정(TODO). 추가 시
`Authorization: Bearer <token>` 헤더만 추가하면 되도록 설계 예정.

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| v1.1.0 | 2026-05-11 | `app/` 흡수에 따라 엔드포인트가 `POST /api/v1/chat` 으로 통일. 별도 8001 포트 없어짐 |
| v1.0.0 | 2026-05-11 | 분리된 `mcp/` 서버 시절. `POST /chat` (포트 8001) — **deprecated, 사용 금지** |
