"""카탈로그 검색 비즈니스 로직.

챗봇(LLM function calling) 과 MCP stdio 서버 양쪽에서 호출하는
순수 함수 모음. 모든 함수는 dict 또는 dict 리스트를 반환해 LLM 응답으로
직접 직렬화될 수 있다.

**데이터 출처**: 검색 도구는 모두 ``storage_catalog`` 테이블만 사용한다.
(``backup_status`` 는 조회하지 않는다.)

세션 관리는 함수 내부에서 :func:`database.session_scope` 로 자동 처리하므로
호출자는 DB 세션을 신경 쓸 필요가 없다(LLM 자동 함수 호출과의 호환성).
"""

# PEP 563(``from __future__ import annotations``) 을 쓰면 매개변수 주석이
# 문자열로만 남아, google-genai AFC 가 ``isinstance(value, annotation)`` 할 때
# ``TypeError: isinstance() arg 2 must be a type...`` 가 난다.

import logging
import unicodedata
from typing import Any, Optional

from sqlalchemy import asc, desc, or_

from database import session_scope
from models.storage_catalog import StorageCatalog

logger = logging.getLogger(__name__)

# google-genai AFC 는 호출 전에 인자를 ``isinstance(value, annotation)`` 로
# 검사한다. ``typing.Any`` 는 여기서 쓸 수 없고, ``keyword: str`` 만 두면
# ``null``/숫자 등에서 실패한다. JSON 스칼라(문자열·숫자·null)는 아래 유니온으로
# 받는다. ``null`` 은 ``None`` 이 되어 연도/카테고리 필터 없음으로 처리한다.
_LlmOptionalScalar = str | int | float | None

# LLM 응답 폭주를 막기 위한 하드 캡 (가이드라인: 25k chars 미만).
_MAX_LIMIT = 50
_DEFAULT_LIMIT = 20


def _normalize_keyword(raw: Any) -> str:
    """검색 키워드를 NFC 로 정규화하고 앞뒤 공백을 제거한다.

    DB 와 클라이언트 간 유니코드 정규화(NFC/NFD) 차이로 LIKE 가 빗나가는
    경우를 줄이기 위한 최소 조치이다.

    LLM 이 ``str`` 이 아닌 값을 넘기는 경우가 있어(또는 AFC 인자 검사를
    통과하기 위해 시그니처를 넓힌 뒤), 여기서 **항상 str 로 수렴**시킨다.
    """
    try:
        if raw is None:
            s = ""
        elif isinstance(raw, bool):
            s = ""
        elif isinstance(raw, str):
            s = raw
        elif isinstance(raw, (int, float)):
            if isinstance(raw, float) and not raw.is_integer():
                s = str(raw).strip()
            else:
                s = str(int(raw))
        else:
            s = str(raw)
        return unicodedata.normalize("NFC", s).strip()
    except Exception:  # noqa: BLE001
        logger.warning("_normalize_keyword failed raw=%r", raw, exc_info=True)
        return ""


def _clamp_limit(limit: Optional[Any]) -> int:
    """limit 값을 1~`_MAX_LIMIT` 범위로 보정한다.

    LLM 이 JSON 숫자를 ``float`` 로 넘기는 경우가 있어 ``int`` 만
    가정하지 않는다.
    """
    if limit is None:
        return _DEFAULT_LIMIT
    if isinstance(limit, bool):
        return _DEFAULT_LIMIT
    try:
        n = int(float(str(limit).strip()))
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


def _coerce_optional_category(category: Any) -> Optional[str]:
    """카테고리 필터 문자열을 만든다. 잘못된 타입이면 None (필터 없음)."""
    if category is None:
        return None
    if isinstance(category, bool):
        return None
    if isinstance(category, str):
        t = category.strip()
        return t or None
    if isinstance(category, (int, float)):
        if isinstance(category, float) and not category.is_integer():
            return str(category).strip() or None
        return str(int(category))
    try:
        t = str(category).strip()
    except Exception:  # noqa: BLE001
        return None
    return t or None


def _coerce_optional_year(year: Any) -> Optional[int]:
    """연도 필터를 정수로 맞춘다. 잘못된 값이면 필터 없음(None)으로 무시한다."""
    if year is None:
        return None
    if isinstance(year, bool):
        return None
    try:
        if isinstance(year, str):
            s = year.strip()
            if not s:
                return None
            return int(float(s))
        return int(float(year))
    except (TypeError, ValueError):
        return None


def _failure_payload_for_llm(base: dict[str, Any]) -> dict[str, Any]:
    """도구 예외 시 LLM 으로 넘길 dict 를 만든다.

    ``error`` 키에 DB 예외 전체를 넣으면 모델이 '시스템 오류' 등으로
    과장해 답하는 경우가 있어, **기술 문자열은 넣지 않는다.** (서버 로그에만
    ``logger.exception`` 으로 남긴다.)
    """
    out = dict(base)
    out["lookup_failed"] = True
    out["message"] = (
        "카탈로그를 조회하지 못했습니다. "
        "일시적인 문제일 수 있으니 잠시 후 다시 시도해 주세요."
    )
    return out


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


def _order_storage_catalog_year_month_id(query: Any) -> Any:
    """연·월 내림차순 + id 내림차순 정렬. NULL 연·월 은 **맨 뒤**로 보낸다.

    SQLAlchemy ``Column.desc().nullslast()`` 는 ``ORDER BY ... NULLS LAST`` 로
    컴파일되는데, 운영 **MySQL** 은 해당 구문을 지원하지 않아 1064 오류가 난다.
    ``(col IS NULL) ASC, col DESC`` 패턴으로 동일 의미를 맞춘다.
    """
    return query.order_by(
        asc(StorageCatalog.year.is_(None)),
        desc(StorageCatalog.year),
        asc(StorageCatalog.month.is_(None)),
        desc(StorageCatalog.month),
        desc(StorageCatalog.id),
    )


def _order_storage_catalog_year_id(query: Any) -> Any:
    """연도·id 내림차순. NULL 연도는 맨 뒤 (MySQL 호환)."""
    return query.order_by(
        asc(StorageCatalog.year.is_(None)),
        desc(StorageCatalog.year),
        desc(StorageCatalog.id),
    )


def find_video_backup_location(
    keyword: _LlmOptionalScalar = None,
    year: _LlmOptionalScalar = None,
    category: _LlmOptionalScalar = None,
    limit: _LlmOptionalScalar = None,
) -> dict[str, Any]:
    """활동명 키워드로 영상 백업 위치를 조회한다.

    - **조회 테이블**: ``storage_catalog`` 만 대상이다.
    - ``activity_name`` 및 ``storage_catalog.description`` 에 부분 일치
      (LIKE, 대소문자 무시)한다.
    - ``search_by_description`` 과의 차이: 여기는 **연도·카테고리 필터**를
      줄 수 있고, 설명 위주 질문은 ``search_by_description`` 을 쓰면 된다.
      (둘 다 ``storage_catalog`` 만 본다.)

    자동 함수 호출 중 DB 예외가 나면 **예외는 삼키고** ``lookup_failed`` 와
    짧은 ``message`` 만 모델에 넘긴다. (기술 예외 문자열은 모델이 과장
    응답하는 원인이 되어 제외한다. 상세는 서버 로그에 남는다.)

    Args:
        keyword: 활동명/별칭 키워드. (예: ``"가족초청예배"``, ``"가초예"``)
            ``None``/빈 값이면 결과 없음. LLM 이 숫자 등으로 줄 수 있어
            ``str | int | float | None`` 을 받는다.
        year: 연도 필터. **선택** — ``None``/JSON ``null``/생략이면 **모든 연도**.
            숫자·문자열 연도는 정수로 보정한다.
        category: 카테고리 필터(예: ``"ACTIVITY"``). **선택** —
            ``None``/JSON ``null``/생략이면 **카테고리 무시**.
        limit: 최대 결과 수. ``None``/JSON ``null``/생략이면 기본 20, 최대 50.

    Returns:
        ``{"keyword": str, "count": int, "items": [ ... ]}`` 형태의 dict.
        실패 시 ``lookup_failed``, ``message`` 와 빈 ``items`` 를 포함한다.
    """
    keyword_n = _normalize_keyword(keyword)
    if not keyword_n:
        return {"keyword": "", "count": 0, "items": []}

    try:
        capped = _clamp_limit(limit)
        year_i = _coerce_optional_year(year)
        pattern = f"%{keyword_n}%"

        with session_scope() as session:
            query = session.query(StorageCatalog).filter(
                or_(
                    StorageCatalog.activity_name.ilike(pattern),
                    StorageCatalog.description.ilike(pattern),
                )
            )
            if year_i is not None:
                query = query.filter(StorageCatalog.year == year_i)
            cat_s = _coerce_optional_category(category)
            if cat_s:
                query = query.filter(StorageCatalog.category == cat_s)

            rows = (
                _order_storage_catalog_year_month_id(query)
                .limit(capped)
                .all()
            )
            items = [_catalog_to_dict(r) for r in rows]

        return {"keyword": keyword_n, "count": len(items), "items": items}
    except Exception:  # noqa: BLE001 — 도구는 절대 raise 하지 않는다.
        logger.exception(
            "find_video_backup_location failed keyword=%r", keyword_n
        )
        return _failure_payload_for_llm(
            {"keyword": keyword_n, "count": 0, "items": []}
        )


def search_by_description(
    keyword: _LlmOptionalScalar = None,
    limit: _LlmOptionalScalar = None,
) -> dict[str, Any]:
    """``storage_catalog.description`` 에서 키워드를 검색한다.

    **조회 테이블**: ``storage_catalog`` 만 대상이다. (``backup_status`` 미사용)

    장면·소스·별칭 등 **설명 문구** 위주로 찾을 때 쓴다.
    ``find_video_backup_location`` 과 달리 ``description`` 컬럼만 본다.
    (활동명 중심·연도 필터는 ``find_video_backup_location`` 쪽이 적합하다.)

    Args:
        keyword: ``storage_catalog.description`` 에 부분 일치시킬 값.
            ``str | int | float | None`` (AFC 인자 검사 통과용).
        limit: 최대 결과 수. ``None``/JSON ``null``/생략이면 기본 20.

    Returns:
        ``catalog_matches``: 매칭된 카탈로그 행 목록.
        ``backup_matches``: **호환용**으로 항상 빈 배열이다. (예전 백업
        테이블 조회 API 를 쓰던 클라이언트가 깨지지 않도록 유지.)
        실패 시 ``lookup_failed``, ``message`` 와 빈 ``catalog_matches`` 를
        포함한다.
    """
    keyword_n = _normalize_keyword(keyword)
    if not keyword_n:
        return {"keyword": "", "catalog_matches": [], "backup_matches": []}

    try:
        capped = _clamp_limit(limit)
        pattern = f"%{keyword_n}%"

        with session_scope() as session:
            catalog_rows = (
                _order_storage_catalog_year_id(
                    session.query(StorageCatalog).filter(
                        StorageCatalog.description.ilike(pattern)
                    )
                )
                .limit(capped)
                .all()
            )
            catalog_matches = [_catalog_to_dict(r) for r in catalog_rows]

        return {
            "keyword": keyword_n,
            "catalog_matches": catalog_matches,
            "backup_matches": [],
        }
    except Exception:  # noqa: BLE001
        logger.exception(
            "search_by_description failed keyword=%r", keyword_n
        )
        base = _failure_payload_for_llm(
            {
                "keyword": keyword_n,
                "catalog_matches": [],
                "backup_matches": [],
            }
        )
        return base


def list_storages() -> dict[str, Any]:
    """등록된 저장소(`storage`) 목록을 중복 없이 반환한다.

    LLM 이 "어떤 저장소가 있어?" 같은 메타 질문을 처리할 때 사용한다.
    """
    try:
        with session_scope() as session:
            rows = (
                session.query(StorageCatalog.storage)
                .distinct()
                .order_by(StorageCatalog.storage.asc())
                .all()
            )
        storages = [r[0] for r in rows if r[0]]
        return {"count": len(storages), "storages": storages}
    except Exception:  # noqa: BLE001
        logger.exception("list_storages failed")
        return _failure_payload_for_llm({"count": 0, "storages": []})


def list_recent_activities(limit: _LlmOptionalScalar = None) -> dict[str, Any]:
    """최근 등록된 활동(카탈로그) 목록을 반환한다.

    LLM 이 처음 대화를 시작할 때 컨텍스트를 잡기 위해 사용 가능.

    Args:
        limit: 최대 건수. ``None``/JSON ``null``/생략이면 기본 20.
    """
    try:
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
    except Exception:  # noqa: BLE001
        logger.exception("list_recent_activities failed limit=%s", limit)
        return _failure_payload_for_llm({"count": 0, "items": []})


# google-genai 의 automatic function calling 에 그대로 넘길 수 있도록
# "도구 함수" 들을 묶어둔다. 함수명이 곧 LLM tool name = MCP tool name.
TOOL_FUNCTIONS = [
    find_video_backup_location,
    search_by_description,
    list_storages,
    list_recent_activities,
]
