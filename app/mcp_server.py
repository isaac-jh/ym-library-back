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
    keyword: Optional[str | int | float] = None,
    year: Optional[str | int | float] = None,
    category: Optional[str | int | float] = None,
    limit: Optional[str | int | float] = None,
) -> dict[str, Any]:
    """활동명/별칭 키워드로 영상 백업 위치를 찾는다.

    ``year``/``category``/``limit`` 는 생략하거나 JSON ``null`` 로 두면
    해당 조건 없이 검색한다.
    `storage_catalog` 에서 매칭되는 영상의 저장소(storage)/연도/월/활동명을
    돌려준다. 결과는 연도 내림차순으로 정렬된다.
    """
    logger.info("find_video_backup_location keyword=%r year=%s", keyword, year)
    return _find_video_backup_location(
        keyword=keyword, year=year, category=category, limit=limit
    )


@mcp.tool()
def search_by_description(
    keyword: Optional[str | int | float] = None,
    limit: Optional[str | int | float] = None,
) -> dict[str, Any]:
    """``storage_catalog.description`` 에서 장면/소스 키워드를 검색한다.

    예: ``keyword="손을 들고 찬양"`` 이면 해당 문구가 description 에 포함된
    카탈로그 행을 돌려준다. 응답의 ``backup_matches`` 는 API 호환용으로
    항상 빈 배열이다.
    """
    logger.info("search_by_description keyword=%r", keyword)
    return _search_by_description(keyword=keyword, limit=limit)


@mcp.tool()
def list_storages() -> dict[str, Any]:
    """등록된 저장소(NAS/CLOUD 등) 목록을 반환한다."""
    return _list_storages()


@mcp.tool()
def list_recent_activities(limit: Optional[str | int | float] = None) -> dict[str, Any]:
    """가장 최근에 등록된 활동(카탈로그) 목록을 반환한다."""
    return _list_recent_activities(limit=limit)


def main() -> None:
    """엔트리포인트. 기본 stdio 트랜스포트로 서버를 띄운다."""
    logger.info("Starting MCP server: %s", _settings.mcp_server_name)
    mcp.run()


if __name__ == "__main__":
    main()
