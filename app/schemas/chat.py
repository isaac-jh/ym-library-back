"""챗봇 API 요청/응답 스키마."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    """대화 한 턴.

    Attributes:
        role: ``user`` 또는 ``model``. 그 외 값은 user 로 강제됨.
        content: 메시지 본문 (텍스트).
    """

    role: str = Field(description="user | model")
    content: str = Field(description="메시지 본문 (텍스트)")


class ChatRequest(BaseModel):
    """`POST /api/v1/chat` 요청 바디.

    Attributes:
        message: 사용자 입력 메시지.
        history: 이전 대화 히스토리(오래된 순). 비어있거나 누락 가능.
    """

    message: str = Field(min_length=1, description="사용자 입력 메시지")
    history: Optional[list[ChatTurn]] = Field(
        default=None, description="이전 대화 히스토리 (오래된 순)"
    )


class ToolCallRecord(BaseModel):
    """LLM 이 호출한 도구 기록(디버깅/감사용)."""

    name: str
    args: dict


class ChatResponse(BaseModel):
    """`POST /api/v1/chat` 응답 바디.

    Attributes:
        reply: 모델이 생성한 한국어 답변 본문.
        tool_calls: 답변 생성 과정에서 호출된 도구 목록.
    """

    reply: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
