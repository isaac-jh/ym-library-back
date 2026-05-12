"""`services.catalog_search` 단위 테스트."""

from __future__ import annotations

from services import catalog_search


def test_find_by_activity_name_korean() -> None:
    """활동명 풀네임으로 검색하면 두 해 분량이 모두 잡혀야 한다."""
    result = catalog_search.find_video_backup_location(keyword="가족초청예배")
    assert result["count"] >= 2
    years = sorted({item["year"] for item in result["items"] if item["year"]})
    assert years == [2024, 2025]


def test_find_by_alias_in_description() -> None:
    """description 안에 들어있는 별칭(가초예) 으로도 검색되어야 한다."""
    result = catalog_search.find_video_backup_location(keyword="가초예")
    storages = {item["storage"] for item in result["items"]}
    # 'NAS-A' 는 description 에 '가초예' 가 명시되어 있다.
    assert "NAS-A" in storages


def test_find_with_year_filter() -> None:
    """year 필터가 정상 동작한다."""
    result = catalog_search.find_video_backup_location(
        keyword="가족초청예배", year=2025
    )
    assert result["count"] == 1
    assert result["items"][0]["year"] == 2025
    assert result["items"][0]["storage"] == "NAS-B"


def test_find_empty_keyword() -> None:
    """빈 키워드는 빈 결과로 안전하게 반환."""
    result = catalog_search.find_video_backup_location(keyword="")
    assert result == {"keyword": "", "count": 0, "items": []}


def test_find_keyword_none_is_empty() -> None:
    """AFC 가 keyword 를 생략하거나 null 로 줄 때도 예외 없이 빈 결과."""
    result = catalog_search.find_video_backup_location(keyword=None)
    assert result == {"keyword": "", "count": 0, "items": []}


def test_find_keyword_int_coerced_to_str() -> None:
    """숫자만 넘어와도 str 로 정규화되어 AFC 인자 검사와 동작이 맞는다."""
    result = catalog_search.find_video_backup_location(keyword=2024)
    assert result["keyword"] == "2024"


def test_find_year_category_null_same_as_omit() -> None:
    """JSON null 과 동일한 ``None`` 이면 연도·카테고리 필터를 쓰지 않는다."""
    baseline = catalog_search.find_video_backup_location(keyword="가족초청예배")
    explicit = catalog_search.find_video_backup_location(
        keyword="가족초청예배",
        year=None,
        category=None,
        limit=20,
    )
    assert explicit.get("lookup_failed") is not True
    assert baseline["count"] == explicit["count"]


def test_genai_afc_invokes_with_json_null_args() -> None:
    """google-genai AFC 인자 변환기가 ``year``/``category`` null 과 함께 호출 가능."""
    from google.genai import _extra_utils

    args = {
        "keyword": "가초예",
        "year": None,
        "category": None,
        "limit": 20,
    }
    out = _extra_utils.invoke_function_from_dict_args(
        args, catalog_search.find_video_backup_location
    )
    assert isinstance(out, dict)
    assert out.get("lookup_failed") is not True
    assert out.get("count", 0) >= 1


def test_search_by_description_hits_catalog_description() -> None:
    """``storage_catalog.description`` 에서만 매칭한다."""
    result = catalog_search.search_by_description(keyword="손을 들고 찬양")
    # 시드: CLOUD 행 description '회중이 손을 들고 찬양하는 장면 다수 포함'
    assert any(item["storage"] == "CLOUD" for item in result["catalog_matches"])
    assert result["backup_matches"] == []


def test_search_by_description_backup_matches_always_empty() -> None:
    """백업 테이블은 조회하지 않으므로 backup_matches 는 항상 빈 배열이다."""
    result = catalog_search.search_by_description(keyword="손을 들고 찬양")
    assert result["backup_matches"] == []


def test_search_by_description_other_catalog_row() -> None:
    """다른 카탈로그 행의 description 도 검색된다."""
    result = catalog_search.search_by_description(keyword="야외 찬양")
    assert any(item["storage"] == "NAS-C" for item in result["catalog_matches"])
    assert result["backup_matches"] == []


def test_list_storages() -> None:
    """저장소 목록은 중복 제거되어야 한다."""
    result = catalog_search.list_storages()
    assert result["count"] == len(result["storages"])
    assert set(result["storages"]) >= {"NAS-A", "NAS-B", "NAS-C", "CLOUD"}


def test_list_recent_activities_limit() -> None:
    """limit 파라미터가 적용된다."""
    result = catalog_search.list_recent_activities(limit=2)
    assert result["count"] == 2
