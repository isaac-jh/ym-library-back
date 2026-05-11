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
#
# 주의: ``system_instruction`` 파라미터로 직접 넘기지 않는다. Gemma 계열
# (예: gemma-4-31b-it) 모델은 system role 을 native 지원하지 않아 Google AI
# Studio API 가 500 INTERNAL 을 반환한다. 대신 :func:`_to_contents` 에서
# 첫 user/model 페어로 변환해 prepend 한다. Gemini 모델도 이 방식을 그대로
# 받아들이므로 **모델 교체 시에도 코드 변경이 필요 없다.**
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

# 시스템 지시 다음에 모델이 인사한 것처럼 보여 주는 가상 응답.
# user/model 페어를 만들어 두면 이후 실제 user 메시지가 자연스럽게 이어진다.
_SYSTEM_ACK = "네, YM Library 영상 카탈로그 검색 도우미입니다. 무엇을 찾아드릴까요?"


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

    Gemma 호환을 위해 **시스템 지시를 첫 user/model 페어로 변환**해
    가장 앞에 prepend 한다. role 은 ``user`` 또는 ``model`` 두 가지만
    허용한다(Gemma/Gemini 공통 규약).
    """
    # 시스템 지시를 user 가 말한 것처럼, 모델이 답한 것처럼 페어로 prepend.
    # 이 방식은 system role 미지원인 Gemma 에서도 500 없이 동작한다.
    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=SYSTEM_INSTRUCTION)],
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text=_SYSTEM_ACK)],
        ),
    ]
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

    # system_instruction 은 의도적으로 사용하지 않는다 (Gemma 호환 — 모듈
    # docstring 참조). 대신 _to_contents 가 첫 user/model 페어로 변환해 둠.
    config = types.GenerateContentConfig(
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
