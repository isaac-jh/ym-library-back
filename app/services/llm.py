"""Google AI Studio (Gemma 4) 호출 래퍼.

`google-genai` SDK 를 통해 **automatic function calling** 모드로
챗봇 한 턴을 처리한다. 도구 함수들은
:data:`services.catalog_search.TOOL_FUNCTIONS` 에서 가져온다.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from google import genai
from google.genai import types

from config import get_settings
from services.catalog_search import TOOL_FUNCTIONS

logger = logging.getLogger(__name__)


# 챗봇 페르소나. 사용자 룰("한글로 대답해줘") 반영.
SYSTEM_INSTRUCTION = """
당신은 'YM Library' 영상 카탈로그 검색 어시스턴트입니다.
사용자는 카탈로그 페이지에서 영상의 백업 위치, 또는 특정 장면이 담긴
영상을 한국어로 자유롭게 질문합니다.

규칙:
1. 답변은 항상 **한국어**로 합니다.
2. 도구(tools) 결과만 근거로 답합니다. 결과가 비어있으면 솔직히 모른다고
   말하고, 더 구체적인 키워드를 요청합니다. 절대로 추측해서 만들어내지 마세요.
3. 영상 위치 질문은 `find_video_backup_location` 을, 장면/소스 질문은
   `search_by_description` 을 우선 사용하세요.
4. 결과가 여러 건이면 **연도/저장소별로 묶어** 항목 형태로 정리합니다.
5. 답변에는 storage(저장소), year, activity_name 또는 name 을 함께
   표기해 사용자가 바로 찾아갈 수 있게 합니다.
6. 친절하고 간결하게, 불필요한 사족 없이 답하세요.
""".strip()


@lru_cache
def get_client() -> genai.Client:
    """`google-genai` 클라이언트 싱글턴.

    `GOOGLE_API_KEY` 환경변수가 설정되어 있어야 한다.
    """
    settings = get_settings()
    if not settings.google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY 가 설정되지 않았습니다. .env 를 확인하세요."
        )
    return genai.Client(api_key=settings.google_api_key)


def _to_contents(
    message: str,
    history: Optional[list[dict[str, str]]] = None,
) -> list[types.Content]:
    """프론트의 `{role, content}` 메시지 리스트를 SDK contents 로 변환.

    role 은 ``user`` 또는 ``model`` 두 가지만 허용한다(Gemma 규약).
    """
    contents: list[types.Content] = []
    for turn in history or []:
        role = (turn.get("role") or "user").lower()
        if role not in ("user", "model"):
            role = "user"
        text = turn.get("content") or ""
        if not text:
            continue
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=text)])
        )
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    )
    return contents


def chat_once(
    message: str,
    history: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """한 번의 챗 턴을 처리한다 (자동 함수 호출 포함).

    Args:
        message: 사용자 입력 메시지.
        history: 이전 대화 히스토리(``[{"role": "user"|"model",
            "content": str}, ...]``). None 이면 새 대화.

    Returns:
        ``{"reply": str, "tool_calls": [{"name": str, "args": dict}, ...]}``.
        ``tool_calls`` 는 디버깅/감사용으로 함께 돌려준다.
    """
    settings = get_settings()
    client = get_client()
    contents = _to_contents(message, history)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOL_FUNCTIONS,
        temperature=0.2,
        # automatic_function_calling 은 기본 활성. 안전을 위해 호출 횟수
        # 상한만 보수적으로 설정.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=6,
        ),
    )

    response = client.models.generate_content(
        model=settings.gemma_model,
        contents=contents,
        config=config,
    )

    reply_text = (response.text or "").strip()

    # 자동 호출된 도구 추적 (디버깅용).
    tool_calls: list[dict[str, Any]] = []
    afc_history = getattr(response, "automatic_function_calling_history", None) or []
    for content in afc_history:
        for part in getattr(content, "parts", None) or []:
            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", None):
                tool_calls.append(
                    {"name": fc.name, "args": dict(getattr(fc, "args", {}) or {})}
                )

    if not reply_text:
        # 모델이 빈 응답을 줬을 때의 폴백.
        reply_text = (
            "죄송합니다. 적절한 결과를 찾지 못했습니다. "
            "키워드를 조금 더 구체적으로 알려주실 수 있을까요?"
        )

    return {"reply": reply_text, "tool_calls": tool_calls}
