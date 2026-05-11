"""챗봇 라우터(`/api/v1/chat`) 단위 테스트.

LLM(Gemma) 호출은 외부 네트워크/API 키가 필요하므로 monkeypatch 로
:func:`services.llm.chat_once` 를 모킹한다.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_app() -> FastAPI:
    """라우터만 마운트한 최소 FastAPI 앱.

    `main.py` 는 lifespan 에서 실제 DB 연결을 강제하므로 테스트에는 부적합.
    """
    from routers import chat as chat_router

    app = FastAPI(redirect_slashes=False)
    app.include_router(chat_router.router, prefix="/api/v1")
    return app


def test_health_endpoint() -> None:
    """헬스 체크는 200 OK 와 model 이름을 반환."""
    client = TestClient(_make_test_app())
    res = client.get("/api/v1/chat/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "model" in body


def test_chat_endpoint_uses_llm(monkeypatch) -> None:
    """챗 엔드포인트가 services.llm.chat_once 결과를 그대로 응답한다."""
    from routers import chat as chat_router

    def _fake_chat_once(message: str, history):  # noqa: ARG001
        return {
            "reply": f"Echo: {message}",
            "tool_calls": [
                {"name": "find_video_backup_location", "args": {"keyword": "가초예"}}
            ],
        }

    monkeypatch.setattr(chat_router, "chat_once", _fake_chat_once)

    client = TestClient(_make_test_app())
    res = client.post(
        "/api/v1/chat",
        json={
            "message": "가초예 영상 어디 있어?",
            "history": [
                {"role": "user", "content": "안녕"},
                {"role": "model", "content": "안녕하세요!"},
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "Echo: 가초예 영상 어디 있어?"
    assert body["tool_calls"][0]["name"] == "find_video_backup_location"
    assert body["tool_calls"][0]["args"] == {"keyword": "가초예"}


def test_chat_endpoint_validation_error() -> None:
    """빈 message 는 422 검증 오류."""
    client = TestClient(_make_test_app())
    res = client.post("/api/v1/chat", json={"message": ""})
    assert res.status_code == 422
