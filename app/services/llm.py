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
from google.genai import errors as genai_errors
from google.genai import types

from config import get_settings
from services.catalog_search import TOOL_FUNCTIONS

logger = logging.getLogger(__name__)


# 챗봇 페르소나. 사용자 룰("한글로 대답해줘") 반영.
#
# 주의: ``system_instruction`` API 필드는 Gemma 에서 500 INTERNAL 이 난다.
# 가짜 ``model`` 턴을 앞에 붙이는 방식도 Gemma+도구 조합에서 500 이 재현됐다.
# 운영에서 검증된 패턴은 **도구만 있고 단일 user 발화**([3] 성공)이므로,
# 시스템 지시는 **마지막 user 메시지 본문에만 인라인**으로 붙인다.
SYSTEM_INSTRUCTION = """
당신은 'YM Library' 영상 카탈로그 검색 어시스턴트입니다.
사용자는 카탈로그 페이지에서 영상의 백업 위치, 또는 특정 장면이 담긴
영상을 한국어로 자유롭게 질문합니다.

규칙:
1. 답변은 항상 **한국어**로 합니다.
2. 도구(tools) 결과만 근거로 답합니다. ``lookup_failed`` 가 true 이면
   조회에 실패한 것이니 재시도를 안내하고, 과장된 '시스템 장애' 표현은
   피합니다. 결과가 비어 있고 실패도 아니면 솔직히 모른다고 말하고,
   더 구체적인 키워드를 요청합니다. 절대로 추측해서 만들어내지 마세요.
3. 도구 선택(매우 중요) — **둘 다 ``storage_catalog`` 테이블만** 본다.
   - ``find_video_backup_location``: ``activity_name`` 과 ``description`` 에
     LIKE 검색. **연도·카테고리 필터는 선택**이다. JSON ``null`` 이거나
     인자를 생략하면 해당 조건 없이(전체 연도·전체 카테고리) 검색한다.
     ``limit`` 도 선택이며 생략 시 기본값을 쓴다.
   - ``search_by_description``: **``description`` 컬럼만** LIKE 검색.
     장면·소스 같은 **설명 문구** 위주 질문이면 이 도구를 쓴다.
   - 한 질문에 대해 두 도구를 **연달아** 호출해도 된다. 첫 도구가 빈 결과면
     다른 컬럼/검색 방식을 의심하고 두 번째를 호출한다.
4. 결과가 여러 건이면 **연도/저장소별로 묶어** 항목 형태로 정리합니다.
5. 답변에는 storage(저장소), year, activity_name 또는 name 을 함께
   표기해 사용자가 바로 찾아갈 수 있게 합니다.
6. 친절하고 간결하게, 불필요한 사족 없이 답하세요.
""".strip()

def _model_is_gemma(model_id: str) -> bool:
    """Google AI Studio 모델 ID 가 Gemma 계열인지 판별한다.

    Gemma 는 ``system_instruction``·긴 인라인 시스템·가짜 model 턴 등과
    조합될 때 API 가 500 INTERNAL 을 내는 사례가 있어, 호출 형태를 분기한다.
    """
    return "gemma" in (model_id or "").lower()


# Gemma 전용: 운영에서 ``tools`` 만 있고 짧은 user 한 줄일 때만 성공했으므로
# 시스템 문구는 **짧은 한 블록**으로만 붙인다. (긴 SYSTEM_INSTRUCTION + 도구 → 500)
_GEMMA_COMPACT_HINT = (
    "한국어로 답해. 도구만 사용(둘 다 storage_catalog): "
    "활동명 검색은 find_video_backup_location(year/category는 null 가능), "
    "장면 설명 키워드는 search_by_description(description만). "
    "결과 없으면 모른다고 해.\n\n"
)


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
    *,
    model_id: str,
    gemma_minimal: bool = False,
) -> list[types.Content]:
    """프론트의 `{role, content}` 메시지 리스트를 SDK contents 로 변환.

    - **Gemini**: 시스템 문구는 ``GenerateContentConfig.system_instruction`` 으로
      넘기므로, 여기서는 ``history`` + 마지막 사용자 질문만 둔다.
    - **Gemma**: ``system_instruction`` 미지원·긴 인라인+도구 시 500 이므로
      마지막 user 턴에 ``_GEMMA_COMPACT_HINT`` 만 짧게 붙인다.
      ``gemma_minimal=True`` 이면 히스토리 없이 **질문 원문만** (폴백 재시도).

    role 은 ``user`` 또는 ``model`` 만 허용한다.
    """
    contents: list[types.Content] = []
    if not gemma_minimal:
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

    stripped = (message or "").strip()
    if _model_is_gemma(model_id):
        final_user_text = stripped if gemma_minimal else f"{_GEMMA_COMPACT_HINT}{stripped}"
    else:
        final_user_text = stripped

    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=final_user_text)])
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
    model_id = settings.gemma_model

    # Gemma: system_instruction 미사용. Gemini: API 가 지원하므로 사용.
    config_kwargs: dict[str, Any] = {
        "tools": TOOL_FUNCTIONS,
        "temperature": 0.2,
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=6,
        ),
    }
    if not _model_is_gemma(model_id):
        config_kwargs["system_instruction"] = SYSTEM_INSTRUCTION

    config = types.GenerateContentConfig(**config_kwargs)

    contents = _to_contents(message, history, model_id=model_id)

    def _call(contents_arg: list[types.Content]) -> Any:
        return client.models.generate_content(
            model=model_id,
            contents=contents_arg,
            config=config,
        )

    try:
        response = _call(contents)
    except genai_errors.ServerError as exc:
        # Gemma: 긴 대화+도구 조합에서 간헐적 500 → 히스토리 제거·질문만 재시도.
        if _model_is_gemma(model_id):
            logger.warning(
                "Gemma generate_content ServerError, retry minimal: %s", exc
            )
            minimal = _to_contents(
                message, history, model_id=model_id, gemma_minimal=True
            )
            response = _call(minimal)
        else:
            raise

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
