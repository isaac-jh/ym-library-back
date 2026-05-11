"""카탈로그 페이지에서 호출하는 챗봇 HTTP API.

표준 MCP stdio 서버(`mcp_server.py`) 와 별도로, 프론트엔드 챗봇이
바로 호출할 수 있도록 FastAPI HTTP 엔드포인트를 제공한다. 내부적으로는
:mod:`llm` (Gemma 4) 를 통해 :mod:`tools` 의 함수들을 자동 호출한다.

엔드포인트
~~~~~~~~~~

* ``POST /chat`` — 메시지 1턴 처리.
* ``GET  /health`` — 헬스 체크.
"""

from __future__ import annotations

import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import get_settings
from llm import chat_once

logger = logging.getLogger(__name__)


_settings = get_settings()


class ChatTurn(BaseModel):
    """대화 한 턴."""

    role: str = Field(
        description="`user` 또는 `model`. 그 외 값은 user 로 강제된다."
    )
    content: str = Field(description="메시지 본문 (텍스트)")


class ChatRequest(BaseModel):
    """`POST /chat` 요청 바디."""

    message: str = Field(min_length=1, description="사용자 입력 메시지")
    history: Optional[list[ChatTurn]] = Field(
        default=None, description="이전 대화 히스토리(오래된 순)"
    )


class ToolCallRecord(BaseModel):
    """LLM 이 호출한 도구 기록(디버깅/감사용)."""

    name: str
    args: dict


class ChatResponse(BaseModel):
    """`POST /chat` 응답 바디."""

    reply: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


app = FastAPI(
    title="YM Library Catalog Chatbot",
    description="영상 백업 위치/장면 검색 챗봇 API",
    version="1.0.0",
    redirect_slashes=False,
)

# CORS — 운영에선 화이트리스트로 제한 권장. (TODO)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """헬스 체크. 모니터링/오케스트레이터용."""
    return {"status": "ok", "model": _settings.gemma_model}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """카탈로그 챗봇 한 턴 처리.

    Args:
        req: 사용자 메시지 + 이전 히스토리.

    Returns:
        :class:`ChatResponse` — 모델 응답 텍스트와 호출된 도구 목록.
    """
    history = [t.model_dump() for t in (req.history or [])]
    try:
        result = chat_once(message=req.message, history=history)
    except RuntimeError as exc:
        # GOOGLE_API_KEY 미설정 등 설정 오류
        logger.exception("chat config error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat handler failed")
        raise HTTPException(status_code=502, detail="LLM 처리 중 오류") from exc

    return ChatResponse(
        reply=result["reply"],
        tool_calls=[ToolCallRecord(**tc) for tc in result.get("tool_calls", [])],
    )


def main() -> None:
    """uvicorn 단독 실행 진입점."""
    uvicorn.run(
        "chat_app:app",
        host=_settings.chat_api_host,
        port=_settings.chat_api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
