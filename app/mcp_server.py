"""FastMCP 기반 MCP stdio 서버 (단독 entrypoint).

Claude Desktop / Cursor / Continue 등 MCP 클라이언트에서 다음과 같이 등록하여
사용할 수 있다(예시는 Claude Desktop ``claude_desktop_config.json``).

.. code-block:: jsonc

    {
      "mcpServers": {
        "ym-library": {
          "command": "/abs/path/to/python",
          "args": ["/abs/path/to/ym-library-back/app/mcp_server.py"],
          "env": {
            "PYTHONPATH": "/abs/path/to/ym-library-back/app",
            "DATABASE_URL": "mysql+pymysql://user:pw@host:3306/ym"
          }
        }
      }
    }

stdio 트랜스포트는 stdout 을 프로토콜 채널로 점유하므로, 모든 로그는
**stderr** 로 출력해야 한다.

도구 구현은 :mod:`services.catalog_search` 를 그대로 재사용하며,
HTTP 챗봇과 정확히 같은 비즈니스 로직 위에서 동작한다.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from config import get_settings
from services.catalog_search import (
    find_video_backup_location as _find_video_backup_location,
    list_recent_activities as _list_recent_activities,
    list_storages as _list_storages,
    search_by_description as _search_by_description,
)


logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ym-library-mcp")


_settings = get_settings()
mcp = FastMCP(_settings.mcp_server_name)


@mcp.tool()
def find_video_backup_location(
    keyword: str,
    year: Optional[int] = None,
    category: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """활동명/별칭 키워드로 영상 백업 위치를 찾는다.

    예: ``keyword="가족초청예배"`` 또는 ``keyword="가초예"`` 와 같이 호출하면
    `storage_catalog` 에서 매칭되는 영상의 저장소(storage)/연도/월/활동명을
    돌려준다. 결과는 연도 내림차순으로 정렬된다.
    """
    logger.info("find_video_backup_location keyword=%r year=%s", keyword, year)
    return _find_video_backup_location(
        keyword=keyword, year=year, category=category, limit=limit
    )


@mcp.tool()
def search_by_description(
    keyword: str,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """description 컬럼에서 특정 장면/소스가 들어있는 영상을 검색한다.

    예: ``keyword="손을 들고 찬양"`` 으로 호출하면 카탈로그/백업의 description
    필드에 해당 키워드가 포함된 영상을 찾고, 백업 결과에는 매칭되는
    카탈로그 위치(`location_hint`)를 함께 첨부해 돌려준다.
    """
    logger.info("search_by_description keyword=%r", keyword)
    return _search_by_description(keyword=keyword, limit=limit)


@mcp.tool()
def list_storages() -> dict[str, Any]:
    """등록된 저장소(NAS/CLOUD 등) 목록을 반환한다."""
    return _list_storages()


@mcp.tool()
def list_recent_activities(limit: Optional[int] = None) -> dict[str, Any]:
    """가장 최근에 등록된 활동(카탈로그) 목록을 반환한다."""
    return _list_recent_activities(limit=limit)


def main() -> None:
    """엔트리포인트. 기본 stdio 트랜스포트로 서버를 띄운다."""
    logger.info("Starting MCP server: %s", _settings.mcp_server_name)
    mcp.run()


if __name__ == "__main__":
    main()
