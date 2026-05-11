"""챗봇/MCP 가 호출하는 검색 도구 구현체.

비즈니스 로직만 담고, MCP/HTTP 인터페이스는 별도 모듈에서 감싼다.
모든 함수는 **순수 함수** 형태로 dict 또는 dict 리스트를 반환하여
LLM 의 function calling 결과로 그대로 직렬화될 수 있다.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import or_

from db import BackupStatus, StorageCatalog, session_scope


# LLM 응답 폭주를 막기 위한 하드 캡 (가이드라인: 25k chars 미만).
_MAX_LIMIT = 50
_DEFAULT_LIMIT = 20


def _clamp_limit(limit: Optional[int]) -> int:
    """limit 값을 1~`_MAX_LIMIT` 범위로 보정한다."""
    if limit is None:
        return _DEFAULT_LIMIT
    return max(1, min(int(limit), _MAX_LIMIT))


def _catalog_to_dict(row: StorageCatalog) -> dict[str, Any]:
    """`StorageCatalog` 행을 LLM 친화적 dict 로 직렬화."""
    return {
        "id": row.id,
        "storage": row.storage,
        "category": row.category,
        "year": row.year,
        "month": row.month,
        "activity_name": row.activity_name,
        "description": row.description,
    }


def _backup_to_dict(row: BackupStatus) -> dict[str, Any]:
    """`BackupStatus` 행을 LLM 친화적 dict 로 직렬화."""
    return {
        "id": row.id,
        "event_name": row.event_name,
        "name": row.name,
        "description": row.description,
        "displayed_date": (
            row.displayed_date.isoformat() if row.displayed_date else None
        ),
    }


def find_video_backup_location(
    keyword: str,
    year: Optional[int] = None,
    category: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """활동명 키워드로 영상 백업 위치를 조회한다.

    - `storage_catalog.activity_name` 에 부분 일치(LIKE %keyword%)
    - 추가로 `storage_catalog.description` 도 함께 검색하여
      별칭(예: '가초예' → '가족초청예배') 매칭 확률을 높인다.
    - 결과는 연도 내림차순, 같은 연도면 월 내림차순으로 정렬.

    Args:
        keyword: 활동명/별칭 키워드. (예: ``"가족초청예배"``, ``"가초예"``)
        year: 특정 연도로 제한.
        category: 카테고리 필터(예: ``"ACTIVITY"``).
        limit: 최대 결과 수. 기본 20, 최대 50.

    Returns:
        ``{"keyword": str, "count": int, "items": [ ... ]}`` 형태의 dict.
        ``items`` 는 :func:`_catalog_to_dict` 결과 리스트.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return {"keyword": keyword, "count": 0, "items": []}

    capped = _clamp_limit(limit)
    pattern = f"%{keyword}%"

    with session_scope() as session:
        query = session.query(StorageCatalog).filter(
            or_(
                StorageCatalog.activity_name.ilike(pattern),
                StorageCatalog.description.ilike(pattern),
            )
        )
        if year is not None:
            query = query.filter(StorageCatalog.year == year)
        if category:
            query = query.filter(StorageCatalog.category == category)

        rows = (
            query.order_by(
                StorageCatalog.year.desc().nullslast(),
                StorageCatalog.month.desc().nullslast(),
                StorageCatalog.id.desc(),
            )
            .limit(capped)
            .all()
        )
        items = [_catalog_to_dict(r) for r in rows]

    return {"keyword": keyword, "count": len(items), "items": items}


def search_by_description(
    keyword: str,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """description 컬럼에서 장면/소스 키워드를 검색한다.

    `storage_catalog.description` 과 `backup_status.description`/`event_name`/
    `name` 을 모두 LIKE 검색해, 어떤 백업에 해당 장면이 들어있는지를 찾는다.
    `backup_status` 결과는 별도로 카탈로그 위치(storage)를 매칭해 함께 돌려준다.

    매칭 규칙(간단한 휴리스틱, TODO 시맨틱 검색으로 교체):
      1) `storage_catalog.description` LIKE ``%keyword%``
         → 그 행의 storage/위치 정보 자체가 곧 답.
      2) `backup_status.description`/`event_name`/`name` LIKE ``%keyword%``
         → 매칭된 backup 의 `event_name` 으로 다시 storage_catalog 를
            대표 1건 조회해 위치를 첨부한다.

    Args:
        keyword: 장면/소스 키워드. (예: ``"손을 들고 찬양"``)
        limit: 각 카테고리별 최대 결과 수. 기본 20, 최대 50.

    Returns:
        ``{"keyword": str, "catalog_matches": [...], "backup_matches": [...]}``.
        ``backup_matches`` 의 각 항목에는 ``location_hint`` 가 추가된다.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return {"keyword": keyword, "catalog_matches": [], "backup_matches": []}

    capped = _clamp_limit(limit)
    pattern = f"%{keyword}%"

    with session_scope() as session:
        catalog_rows = (
            session.query(StorageCatalog)
            .filter(StorageCatalog.description.ilike(pattern))
            .order_by(StorageCatalog.year.desc().nullslast(), StorageCatalog.id.desc())
            .limit(capped)
            .all()
        )
        catalog_matches = [_catalog_to_dict(r) for r in catalog_rows]

        backup_rows = (
            session.query(BackupStatus)
            .filter(BackupStatus.deleted == False)  # noqa: E712  (SQLAlchemy 비교)
            .filter(
                or_(
                    BackupStatus.description.ilike(pattern),
                    BackupStatus.event_name.ilike(pattern),
                    BackupStatus.name.ilike(pattern),
                )
            )
            .order_by(BackupStatus.displayed_date.desc().nullslast())
            .limit(capped)
            .all()
        )

        backup_matches: list[dict[str, Any]] = []
        for row in backup_rows:
            entry = _backup_to_dict(row)
            # event_name 으로 동일/유사 활동의 카탈로그 위치를 찾아 힌트로 첨부.
            location_hint: Optional[dict[str, Any]] = None
            if row.event_name:
                hint = (
                    session.query(StorageCatalog)
                    .filter(
                        or_(
                            StorageCatalog.activity_name.ilike(f"%{row.event_name}%"),
                            StorageCatalog.description.ilike(f"%{row.event_name}%"),
                        )
                    )
                    .order_by(StorageCatalog.year.desc().nullslast())
                    .first()
                )
                if hint is not None:
                    location_hint = _catalog_to_dict(hint)
            entry["location_hint"] = location_hint
            backup_matches.append(entry)

    return {
        "keyword": keyword,
        "catalog_matches": catalog_matches,
        "backup_matches": backup_matches,
    }


def list_storages() -> dict[str, Any]:
    """등록된 저장소(`storage`) 목록을 중복 없이 반환한다.

    LLM 이 "어떤 저장소가 있어?" 같은 메타 질문을 처리할 때 사용한다.
    """
    with session_scope() as session:
        rows = (
            session.query(StorageCatalog.storage)
            .distinct()
            .order_by(StorageCatalog.storage.asc())
            .all()
        )
    storages = [r[0] for r in rows if r[0]]
    return {"count": len(storages), "storages": storages}


def list_recent_activities(limit: Optional[int] = None) -> dict[str, Any]:
    """최근 등록된 활동(카탈로그) 목록을 반환한다.

    LLM 이 처음 대화를 시작할 때 컨텍스트를 잡기 위해 사용 가능.
    """
    capped = _clamp_limit(limit)
    with session_scope() as session:
        rows = (
            session.query(StorageCatalog)
            .order_by(StorageCatalog.id.desc())
            .limit(capped)
            .all()
        )
        items = [_catalog_to_dict(r) for r in rows]
    return {"count": len(items), "items": items}


# google-genai 의 automatic function calling 에 그대로 넘길 수 있도록
# "도구 함수" 들을 묶어둔다. 이름은 함수명 = MCP tool name = LLM tool name.
TOOL_FUNCTIONS = [
    find_video_backup_location,
    search_by_description,
    list_storages,
    list_recent_activities,
]
