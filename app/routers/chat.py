"""카탈로그 챗봇 API 라우터.

프론트엔드 카탈로그 페이지에서 호출하는 챗봇 엔드포인트를 제공한다.
내부적으로 :func:`services.llm.chat_once` 를 통해 Gemma 4 31B 가
:data:`services.catalog_search.TOOL_FUNCTIONS` 를 자동으로 호출해 답변을
생성한다.

Endpoints
~~~~~~~~~
* ``POST /chat`` — 메시지 1턴 처리.
* ``GET  /chat/health`` — 챗봇 헬스 체크 (모델 ID 함께 반환).
"""

import logging

from fastapi import APIRouter, HTTPException, status

from config import get_settings
from schemas.chat import ChatRequest, ChatResponse, ToolCallRecord
from services.llm import chat_once

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={500: {"description": "Internal error"}},
)


@router.get("/health")
def chat_health() -> dict[str, str]:
    """챗봇 전용 헬스 체크.

    모델 ID 도 함께 반환해, 잘못된 모델 ID 가 배포되었는지 운영 단계에서
    확인할 수 있게 한다.
    """
    settings = get_settings()
    return {"status": "ok", "model": settings.gemma_model}


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """카탈로그 챗봇 한 턴 처리.

    LLM 의 자동 함수 호출(automatic function calling)이 끝난 뒤의
    최종 답변과, 그 과정에서 호출된 도구 목록을 함께 돌려준다.

    Args:
        req: 사용자 메시지 + 이전 히스토리.

    Returns:
        :class:`ChatResponse`.

    Raises:
        HTTPException 500: GOOGLE_API_KEY 미설정 등 설정 오류.
        HTTPException 502: LLM/네트워크 처리 실패.
    """
    history = [t.model_dump() for t in (req.history or [])]
    try:
        result = chat_once(message=req.message, history=history)
    except RuntimeError as exc:
        logger.exception("chat config error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat handler failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM 처리 중 오류"
        ) from exc

    return ChatResponse(
        reply=result["reply"],
        tool_calls=[ToolCallRecord(**tc) for tc in result.get("tool_calls", [])],
    )
