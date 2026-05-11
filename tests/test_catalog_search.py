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


def test_search_by_description_hits_both_tables() -> None:
    """description 키워드가 카탈로그/백업 양쪽에 모두 매칭된다."""
    result = catalog_search.search_by_description(keyword="손을 들고 찬양")
    # 카탈로그: '회중이 손을 들고 찬양하는 장면 다수 포함'
    assert any(item["storage"] == "CLOUD" for item in result["catalog_matches"])


def test_search_by_description_excludes_deleted() -> None:
    """soft-delete 된 backup 은 결과에 포함되면 안 된다."""
    result = catalog_search.search_by_description(keyword="손을 들고 찬양")
    names = {entry["name"] for entry in result["backup_matches"]}
    assert "과거 영상" not in names


def test_search_by_description_attaches_location_hint() -> None:
    """backup 매칭 결과에는 location_hint 가 함께 붙어야 한다."""
    result = catalog_search.search_by_description(keyword="손 든 회중")
    assert len(result["backup_matches"]) >= 1
    entry = result["backup_matches"][0]
    assert "location_hint" in entry
    # event_name '청년부 임직예배' 로부터 'CLOUD' 카탈로그가 매칭되어야 한다.
    if entry["location_hint"] is not None:
        assert entry["location_hint"]["storage"] == "CLOUD"


def test_list_storages() -> None:
    """저장소 목록은 중복 제거되어야 한다."""
    result = catalog_search.list_storages()
    assert result["count"] == len(result["storages"])
    assert set(result["storages"]) >= {"NAS-A", "NAS-B", "NAS-C", "CLOUD"}


def test_list_recent_activities_limit() -> None:
    """limit 파라미터가 적용된다."""
    result = catalog_search.list_recent_activities(limit=2)
    assert result["count"] == 2
