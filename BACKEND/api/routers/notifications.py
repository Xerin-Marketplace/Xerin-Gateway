from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import DeviceToken, Notification, NotificationPreference, NotificationTemplate, User
from api.permissions import require_permission
from api.schemas import (
    DeviceTokenCreate, DeviceTokenResponse, NotificationPreferenceResponse, NotificationPreferenceUpdate,
    NotificationResponse, NotificationSummary, NotificationTemplateCreate, NotificationTemplateResponse,
    NotificationTemplateUpdate,
)
from api.services.notification_service import notification_service

router = APIRouter(tags=["Notifications"])


def _notification_or_404(db: Session, user_id: UUID, notification_id: UUID) -> Notification:
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return item


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(unread_only: bool = False, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_read.value))):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only: query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/notifications/summary", response_model=NotificationSummary)
def notification_summary(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_read.value))):
    total = db.query(Notification).filter(Notification.user_id == current_user.id).count()
    unread = notification_service.unread_count(db, current_user.id)
    return NotificationSummary(total=total, unread=unread, read=total-unread)


@router.patch("/notifications/read-all", response_model=NotificationSummary)
def read_all(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    now = datetime.now(timezone.utc)
    db.query(Notification).filter(Notification.user_id == current_user.id, Notification.is_read.is_(False)).update({Notification.is_read: True, Notification.read_at: now}, synchronize_session=False)
    db.commit()
    total = db.query(Notification).filter(Notification.user_id == current_user.id).count()
    return NotificationSummary(total=total, unread=0, read=total)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    item = _notification_or_404(db, current_user.id, notification_id)
    if not item.is_read: item.is_read=True; item.read_at=datetime.now(timezone.utc); db.commit(); db.refresh(item)
    return item


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    item = _notification_or_404(db, current_user.id, notification_id); db.delete(item); db.commit()


@router.get("/notifications/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_read.value))):
    preference = notification_service.get_or_create_preferences(db, current_user.id); db.commit(); db.refresh(preference); return preference


@router.patch("/notifications/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(data: NotificationPreferenceUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    preference = notification_service.get_or_create_preferences(db, current_user.id)
    for key, value in data.model_dump(exclude_unset=True).items(): setattr(preference, key, value)
    db.commit(); db.refresh(preference); return preference


@router.post("/notifications/device-tokens", response_model=DeviceTokenResponse, status_code=status.HTTP_201_CREATED)
def register_device(data: DeviceTokenCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    token = db.query(DeviceToken).filter(DeviceToken.token == data.token).first()
    if token:
        token.user_id=current_user.id; token.platform=data.platform; token.device_name=data.device_name; token.is_active=True
    else: token=DeviceToken(user_id=current_user.id, **data.model_dump()); db.add(token)
    db.commit(); db.refresh(token); return token


@router.delete("/notifications/device-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(token_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    token=db.query(DeviceToken).filter(DeviceToken.id==token_id, DeviceToken.user_id==current_user.id).first()
    if not token: raise HTTPException(status_code=404, detail="Device token not found")
    db.delete(token); db.commit()


@router.get("/admin/notification-templates", response_model=list[NotificationTemplateResponse])
def list_templates(db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.admin_notifications_read.value))):
    return db.query(NotificationTemplate).order_by(NotificationTemplate.event, NotificationTemplate.channel).all()


@router.post("/admin/notification-templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(data: NotificationTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_notification_templates_manage.value))):
    item=NotificationTemplate(**data.model_dump(), created_by_id=current_user.id); db.add(item)
    try: db.commit(); db.refresh(item); return item
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="Template already exists for this event and channel") from exc


@router.patch("/admin/notification-templates/{template_id}", response_model=NotificationTemplateResponse)
def update_template(template_id: UUID, data: NotificationTemplateUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.admin_notification_templates_manage.value))):
    item=db.query(NotificationTemplate).filter(NotificationTemplate.id==template_id).first()
    if not item: raise HTTPException(status_code=404, detail="Notification template not found")
    for key,value in data.model_dump(exclude_unset=True).items(): setattr(item,key,value)
    db.commit(); db.refresh(item); return item
