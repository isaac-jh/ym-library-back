"""서비스 레이어 패키지.

라우터/MCP 서버 양쪽에서 재사용 가능한 비즈니스 로직을 모아둔다.

- :mod:`services.catalog_search`: 카탈로그/백업 검색 도구 함수.
- :mod:`services.llm`: Google AI Studio (Gemma 4) 챗봇 호출 래퍼.
"""

from services import catalog_search, llm

__all__ = ["catalog_search", "llm"]
