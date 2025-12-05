"""
백업 상태 API 라우터

백업 상태 CRUD 엔드포인트를 제공합니다.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session, aliased

from database import get_db
from models.backup_status import BackupStatus
from models.m_user_backup_status import MUserBackupStatus
from models.user import User
from schemas.backup_status import (
    BackupStatusCreate,
    BackupStatusListResponse,
    BackupStatusResponse,
    BackupStatusUpdate,
)

router = APIRouter(
    prefix="/backup-status",
    tags=["Backup Status"],
    responses={404: {"description": "Not found"}},
)


def get_producers_for_backup(db: Session, backup_status_id: int) -> List[str]:
    """
    백업 상태에 매핑된 작업자(producers) 이름 리스트를 조회합니다.

    Args:
        db: 데이터베이스 세션
        backup_status_id: 백업 상태 ID

    Returns:
        List[str]: 작업자 이름 리스트
    """
    mappings = (
        db.query(MUserBackupStatus, User.name)
        .join(User, MUserBackupStatus.user_id == User.id)
        .filter(MUserBackupStatus.backup_status_id == backup_status_id)
        .all()
    )
    return [mapping.name for mapping in mappings]


def sync_producers(
    db: Session, backup_status_id: int, user_ids: List[int], created_by: int
) -> None:
    """
    백업 상태의 작업자(producers) 매핑을 동기화합니다.

    기존 매핑을 모두 삭제하고 새로운 매핑을 생성합니다.

    Args:
        db: 데이터베이스 세션
        backup_status_id: 백업 상태 ID
        user_ids: 새로 매핑할 사용자 ID 리스트
        created_by: 생성자 ID
    """
    # 기존 매핑 삭제
    db.query(MUserBackupStatus).filter(
        MUserBackupStatus.backup_status_id == backup_status_id
    ).delete()

    # 새 매핑 생성
    for user_id in user_ids:
        mapping = MUserBackupStatus(
            user_id=user_id,
            backup_status_id=backup_status_id,
            created_by=created_by,
        )
        db.add(mapping)


@router.get("/", response_model=List[BackupStatusListResponse])
def get_backup_statuses(
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(100, ge=1, le=1000, description="조회할 항목 수"),
    event_name: Optional[str] = Query(None, description="이벤트명 필터"),
    db: Session = Depends(get_db),
):
    """
    백업 상태 목록을 조회합니다.

    삭제되지 않은 항목만 조회됩니다.
    각 checker 필드에 해당하는 사용자 이름을 함께 반환합니다.
    작업자(producers) 이름 리스트도 함께 반환합니다.
    displayed_date 기준 최신순으로 정렬됩니다.

    - **skip**: 페이지네이션을 위한 건너뛸 항목 수
    - **limit**: 조회할 최대 항목 수
    - **event_name**: 이벤트명으로 필터링
    """
    # 각 checker에 대해 User 테이블을 별도로 alias하여 left join
    CamChecker = aliased(User)
    MasterChecker = aliased(User)
    CleanChecker = aliased(User)
    FinalProductChecker = aliased(User)

    query = (
        db.query(
            BackupStatus,
            CamChecker.name.label("cam_checker_name"),
            MasterChecker.name.label("master_checker_name"),
            CleanChecker.name.label("clean_checker_name"),
            FinalProductChecker.name.label("final_product_checker_name"),
        )
        .outerjoin(CamChecker, BackupStatus.cam_checker == CamChecker.id)
        .outerjoin(MasterChecker, BackupStatus.master_checker == MasterChecker.id)
        .outerjoin(CleanChecker, BackupStatus.clean_checker == CleanChecker.id)
        .outerjoin(
            FinalProductChecker,
            BackupStatus.final_product_checker == FinalProductChecker.id,
        )
    )

    # 삭제되지 않은 항목만 조회
    query = query.filter(BackupStatus.deleted == False)

    if event_name:
        query = query.filter(BackupStatus.event_name.contains(event_name))

    # displayed_date 기준 최신순 정렬 (NULL은 마지막에)
    query = query.order_by(desc(BackupStatus.displayed_date).nullslast())

    results = query.offset(skip).limit(limit).all()

    # 결과를 응답 스키마에 맞게 변환
    response_list = []
    for row in results:
        backup = row[0]  # BackupStatus 객체

        # 작업자(producers) 조회
        producers = get_producers_for_backup(db, backup.id)

        response_list.append(
            BackupStatusListResponse(
                id=backup.id,
                event_name=backup.event_name,
                displayed_date=backup.displayed_date,
                name=backup.name,
                description=backup.description,
                cam=backup.cam,
                cam_checker=backup.cam_checker,
                cam_checker_name=row.cam_checker_name,
                master=backup.master,
                master_checker=backup.master_checker,
                master_checker_name=row.master_checker_name,
                clean=backup.clean,
                clean_checker=backup.clean_checker,
                clean_checker_name=row.clean_checker_name,
                final_product=backup.final_product,
                final_product_checker=backup.final_product_checker,
                final_product_checker_name=row.final_product_checker_name,
                created_at=backup.created_at,
                producers=producers,
            )
        )

    return response_list


@router.get("/{backup_id}", response_model=BackupStatusResponse)
def get_backup_status(backup_id: int, db: Session = Depends(get_db)):
    """
    특정 백업 상태 항목을 조회합니다.

    - **backup_id**: 조회할 백업 상태의 ID
    """
    backup = (
        db.query(BackupStatus)
        .filter(BackupStatus.id == backup_id, BackupStatus.deleted == False)
        .first()
    )
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {backup_id}인 백업 상태를 찾을 수 없습니다.",
        )
    return backup


@router.post(
    "/", response_model=BackupStatusResponse, status_code=status.HTTP_201_CREATED
)
def create_backup_status(
    backup_data: BackupStatusCreate, db: Session = Depends(get_db)
):
    """
    새로운 백업 상태 항목을 생성합니다.

    user_ids가 제공되면 해당 사용자들을 작업자(producers)로 매핑합니다.

    - **backup_data**: 생성할 백업 상태 데이터
    - **backup_data.user_ids**: 작업자로 매핑할 사용자 ID 리스트
    - **backup_data.created_by**: 생성자 ID
    """
    # user_ids와 created_by는 BackupStatus 모델에 없으므로 제외
    backup_dict = backup_data.model_dump(exclude={"user_ids", "created_by"})
    backup = BackupStatus(**backup_dict)
    db.add(backup)
    db.commit()
    db.refresh(backup)

    # 작업자(producers) 매핑 생성
    if backup_data.user_ids:
        sync_producers(db, backup.id, backup_data.user_ids, backup_data.created_by)
        db.commit()

    return backup


@router.put("/{backup_id}", response_model=BackupStatusResponse)
def update_backup_status(
    backup_id: int, backup_data: BackupStatusUpdate, db: Session = Depends(get_db)
):
    """
    백업 상태 항목을 수정합니다.

    user_ids가 제공되면 작업자(producers) 매핑을 갱신합니다.

    - **backup_id**: 수정할 백업 상태의 ID
    - **backup_data**: 수정할 데이터
    - **backup_data.user_ids**: 작업자로 매핑할 사용자 ID 리스트 (전체 교체)
    - **backup_data.updated_by**: 수정자 ID (user_ids 변경 시 필수)
    """
    backup = (
        db.query(BackupStatus)
        .filter(BackupStatus.id == backup_id, BackupStatus.deleted == False)
        .first()
    )
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {backup_id}인 백업 상태를 찾을 수 없습니다.",
        )

    # user_ids와 updated_by는 BackupStatus 모델에 없으므로 제외
    update_data = backup_data.model_dump(
        exclude_unset=True, exclude={"user_ids", "updated_by"}
    )
    for field, value in update_data.items():
        setattr(backup, field, value)

    # 작업자(producers) 매핑 갱신
    if backup_data.user_ids is not None:
        if not backup_data.updated_by:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_ids 변경 시 updated_by는 필수입니다.",
            )
        sync_producers(db, backup_id, backup_data.user_ids, backup_data.updated_by)

    db.commit()
    db.refresh(backup)
    return backup


@router.patch("/{backup_id}/mark-complete", response_model=BackupStatusResponse)
def mark_backup_complete(
    backup_id: int,
    cam: Optional[bool] = Query(None, description="카메라 원본 백업 완료"),
    cam_checker: Optional[int] = Query(None, description="카메라 원본 확인자 ID"),
    master: Optional[bool] = Query(None, description="마스터 백업 완료"),
    master_checker: Optional[int] = Query(None, description="마스터 확인자 ID"),
    clean: Optional[bool] = Query(None, description="정리본 백업 완료"),
    clean_checker: Optional[int] = Query(None, description="정리본 확인자 ID"),
    final_product: Optional[bool] = Query(None, description="최종 산출물 백업 완료"),
    final_product_checker: Optional[int] = Query(
        None, description="최종 산출물 확인자 ID"
    ),
    db: Session = Depends(get_db),
):
    """
    백업 단계별 완료 상태를 업데이트합니다.

    - **backup_id**: 업데이트할 백업 상태의 ID
    - **cam**: 카메라 원본 백업 완료 여부
    - **cam_checker**: 카메라 원본 확인자 ID
    - **master**: 마스터 백업 완료 여부
    - **master_checker**: 마스터 확인자 ID
    - **clean**: 정리본 백업 완료 여부
    - **clean_checker**: 정리본 확인자 ID
    - **final_product**: 최종 산출물 백업 완료 여부
    - **final_product_checker**: 최종 산출물 확인자 ID
    """
    backup = (
        db.query(BackupStatus)
        .filter(BackupStatus.id == backup_id, BackupStatus.deleted == False)
        .first()
    )
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {backup_id}인 백업 상태를 찾을 수 없습니다.",
        )

    if cam is not None:
        backup.cam = cam
    if cam_checker is not None:
        backup.cam_checker = cam_checker
    if master is not None:
        backup.master = master
    if master_checker is not None:
        backup.master_checker = master_checker
    if clean is not None:
        backup.clean = clean
    if clean_checker is not None:
        backup.clean_checker = clean_checker
    if final_product is not None:
        backup.final_product = final_product
    if final_product_checker is not None:
        backup.final_product_checker = final_product_checker

    db.commit()
    db.refresh(backup)
    return backup


@router.delete("/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backup_status(
    backup_id: int,
    deleted_by: int = Query(..., description="삭제를 수행하는 사용자 ID"),
    db: Session = Depends(get_db),
):
    """
    백업 상태 항목을 삭제합니다. (소프트 삭제)

    - **backup_id**: 삭제할 백업 상태의 ID
    - **deleted_by**: 삭제를 수행하는 사용자 ID (필수)
    """
    backup = (
        db.query(BackupStatus)
        .filter(BackupStatus.id == backup_id, BackupStatus.deleted == False)
        .first()
    )
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {backup_id}인 백업 상태를 찾을 수 없습니다.",
        )

    # 소프트 삭제 처리
    backup.deleted = True
    backup.deleted_by = deleted_by

    db.commit()
