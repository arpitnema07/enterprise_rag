from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, auth, database

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("/", response_model=schemas.Group)
def create_group(
    group: schemas.GroupCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    # Only admin can create groups
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to create groups")

    db_group = models.Group(name=group.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)

    # Add creator as manager
    db_user_group = models.UserGroup(
        user_id=current_user.id, group_id=db_group.id, role="manager"
    )
    db.add(db_user_group)
    db.commit()

    return db_group


@router.get("", response_model=List[schemas.Group])
def read_groups(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if current_user.is_admin:
        # Admins can see all groups
        groups = db.query(models.Group).offset(skip).limit(limit).all()
    else:
        # Regular users only see groups they are members of
        user_group_ids = (
            db.query(models.UserGroup.group_id)
            .filter(models.UserGroup.user_id == current_user.id)
            .all()
        )
        group_ids = [ug[0] for ug in user_group_ids]
        groups = (
            db.query(models.Group)
            .filter(models.Group.id.in_(group_ids))
            .offset(skip)
            .limit(limit)
            .all()
        )
    return groups


@router.post("/{group_id}/users/{user_id}", response_model=schemas.UserGroupUnnassigned)
def add_user_to_group(
    group_id: int,
    user_id: int,
    role: str = "member",
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    # Check permissions (only admin or manager of that group)
    # Simplified for now: Only admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    db_user_group = models.UserGroup(user_id=user_id, group_id=group_id, role=role)
    db.add(db_user_group)
    db.commit()
    return db_user_group
