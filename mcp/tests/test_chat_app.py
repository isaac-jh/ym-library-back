"""챗봇 HTTP API 단위 테스트.

LLM(Gemma) 호출은 외부 네트워크/API 키가 필요하므로 monkeypatch 로
:func:`llm.chat_once` 를 모킹한다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import chat_app


def test_health_endpoint() -> None:
    """헬스 체크는 200 OK 와 model 이름을 반환."""
    client = TestClient(chat_app.app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "model" in body


def test_chat_endpoint_uses_llm(monkeypatch) -> None:
    """챗 엔드포인트가 llm.chat_once 결과를 그대로 응답한다."""

    def _fake_chat_once(message: str, history):  # noqa: ARG001
        return {
            "reply": f"Echo: {message}",
            "tool_calls": [
                {"name": "find_video_backup_location", "args": {"keyword": "가초예"}}
            ],
        }

    monkeypatch.setattr(chat_app, "chat_once", _fake_chat_once)

    client = TestClient(chat_app.app)
    res = client.post(
        "/chat",
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
    client = TestClient(chat_app.app)
    res = client.post("/chat", json={"message": ""})
    assert res.status_code == 422
