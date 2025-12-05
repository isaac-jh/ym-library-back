"""
저장소 카탈로그 API 라우터

저장소 카탈로그 CRUD 엔드포인트를 제공합니다.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.storage_catalog import StorageCatalog
from schemas.storage_catalog import (
    StorageCatalogCreate,
    StorageCatalogResponse,
    StorageCatalogUpdate,
)

router = APIRouter(
    prefix="/storage-catalogs",
    tags=["Storage Catalog"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[StorageCatalogResponse])
def get_storage_catalogs(
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(100, ge=1, le=1000, description="조회할 항목 수"),
    storage: Optional[str] = Query(None, description="저장소 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    year: Optional[int] = Query(None, description="연도 필터"),
    db: Session = Depends(get_db),
):
    """
    저장소 카탈로그 목록을 조회합니다.

    - **skip**: 페이지네이션을 위한 건너뛸 항목 수
    - **limit**: 조회할 최대 항목 수
    - **storage**: 저장소 이름으로 필터링
    - **category**: 카테고리로 필터링
    - **year**: 연도로 필터링
    """
    query = db.query(StorageCatalog)

    if storage:
        query = query.filter(StorageCatalog.storage == storage)
    if category:
        query = query.filter(StorageCatalog.category == category)
    if year:
        query = query.filter(StorageCatalog.year == year)

    return query.offset(skip).limit(limit).all()


@router.get("/{catalog_id}", response_model=StorageCatalogResponse)
def get_storage_catalog(catalog_id: int, db: Session = Depends(get_db)):
    """
    특정 저장소 카탈로그 항목을 조회합니다.

    - **catalog_id**: 조회할 카탈로그의 ID
    """
    catalog = db.query(StorageCatalog).filter(StorageCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {catalog_id}인 카탈로그를 찾을 수 없습니다.",
        )
    return catalog


@router.post(
    "/", response_model=StorageCatalogResponse, status_code=status.HTTP_201_CREATED
)
def create_storage_catalog(
    catalog_data: StorageCatalogCreate, db: Session = Depends(get_db)
):
    """
    새로운 저장소 카탈로그 항목을 생성합니다.

    - **catalog_data**: 생성할 카탈로그 데이터
    """
    catalog = StorageCatalog(**catalog_data.model_dump())
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog


@router.put("/{catalog_id}", response_model=StorageCatalogResponse)
def update_storage_catalog(
    catalog_id: int, catalog_data: StorageCatalogUpdate, db: Session = Depends(get_db)
):
    """
    저장소 카탈로그 항목을 수정합니다.

    - **catalog_id**: 수정할 카탈로그의 ID
    - **catalog_data**: 수정할 데이터
    """
    catalog = db.query(StorageCatalog).filter(StorageCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {catalog_id}인 카탈로그를 찾을 수 없습니다.",
        )

    update_data = catalog_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(catalog, field, value)

    db.commit()
    db.refresh(catalog)
    return catalog


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storage_catalog(catalog_id: int, db: Session = Depends(get_db)):
    """
    저장소 카탈로그 항목을 삭제합니다.

    - **catalog_id**: 삭제할 카탈로그의 ID
    """
    catalog = db.query(StorageCatalog).filter(StorageCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {catalog_id}인 카탈로그를 찾을 수 없습니다.",
        )

    db.delete(catalog)
    db.commit()
    return None
