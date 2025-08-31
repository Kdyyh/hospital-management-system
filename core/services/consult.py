from typing import Optional, Tuple, List
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import bleach
from django.conf import settings

from core.models import Consultation, ConsMessage, ConsAttachment, Group
try:
    from core.services.audit import log_action
except Exception:
    def log_action(*args, **kwargs):
        return None

User = get_user_model()

def _is_doctor(user: User) -> bool:
    return getattr(user, 'role', '') in ('admin', 'core')

def _is_patient(user: User) -> bool:
    return getattr(user, 'role', '') == 'patient'

def check_consult_access(user: User, consult: Consultation) -> bool:
    if getattr(user, 'role', '') == 'super':
        return True
    if _is_doctor(user):
        return consult.group_id == getattr(user, 'group_id', None)
    if _is_patient(user):
        return consult.patient_id == user.id
    return False

def open_consult(request_user: User, target_user: User, ctype: Optional[str]=None) -> Consultation:
    if not getattr(request_user, 'group_id', None) or not getattr(target_user, 'group_id', None):
        raise PermissionError('双方必须绑定科室')
    if request_user.group_id != target_user.group_id:
        raise PermissionError('跨科室会话不允许')

    if _is_doctor(request_user) and _is_patient(target_user):
        doctor, patient = request_user, target_user
        ctype = ctype or Consultation.TYPE_DOCTOR
    elif _is_patient(request_user) and _is_doctor(target_user):
        doctor, patient = target_user, request_user
        ctype = ctype or Consultation.TYPE_PATIENT
    else:
        raise PermissionError('仅支持医生(admin/core)与患者(patient)之间对话')

    consult, created = Consultation.objects.get_or_create(
        group_id=request_user.group_id, doctor=doctor, patient=patient,
        defaults={'ctype': ctype}
    )
    return consult

@transaction.atomic
def send_message(consult: Consultation, sender: User, content: str, files: Optional[list]=None) -> ConsMessage:
    if not check_consult_access(sender, consult):
        raise PermissionError('无权访问该会话')

    content = bleach.clean((content or '').strip(), strip=True)
    files = files or []

    if not content and not files:
        raise ValueError('消息不能为空')

    msg = ConsMessage.objects.create(consult=consult, sender=sender, content=content)
    for f in files:
        size_mb = (f.size or 0) / (1024*1024)
        if size_mb > settings.UPLOAD_MAX_MB:
            raise ValueError('文件过大')
        ctype = getattr(f, 'content_type', '') or ''
        if not any([ctype.startswith(prefix) for prefix in settings.ALLOWED_UPLOAD_TYPES]):
            raise ValueError('不支持的文件类型')
        ConsAttachment.objects.create(message=msg, file=f, content_type=ctype, size=f.size or 0)

    consult.last_message_at = timezone.now()
    if sender.id == consult.doctor_id:
        consult.unread_for_patient += 1
        consult.status = Consultation.STATUS_REPLIED if consult.status == Consultation.STATUS_OPEN else consult.status
    else:
        consult.unread_for_doctor += 1
        consult.status = Consultation.STATUS_OPEN
    consult.save(update_fields=['last_message_at','unread_for_doctor','unread_for_patient','status'])

    try:
        log_action(user=sender, action='consult_send', object_type='consult', object_id=consult.id, detail={'msgId': msg.id})
    except Exception:
        pass

    channel_layer = get_channel_layer()
    if channel_layer is not None:
        atts = [{'id': a.id, 'url': a.file.url, 'contentType': a.content_type, 'size': a.size} for a in msg.attachments.all()]
        payload = {
            "type": "consult.message",
            "consultId": consult.id,
            "senderId": sender.id,
            "content": msg.content,
            "messageId": msg.id,
            "createdAt": msg.created_at.isoformat(),
            "attachments": atts,
            "unreadForDoctor": consult.unread_for_doctor,
            "unreadForPatient": consult.unread_for_patient,
            "status": consult.status,
        }
        async_to_sync(channel_layer.group_send)(f"consult.{consult.id}", payload)

    return msg

def list_consults(user: User, *, status: Optional[str]=None, q: Optional[str]=None, dept_id: Optional[int]=None, page: int=1, page_size: int=20):
    qs = Consultation.objects.all()
    if getattr(user, 'role', '') == 'super':
        if dept_id:
            qs = qs.filter(group_id=dept_id)
    elif _is_doctor(user):
        qs = qs.filter(group_id=getattr(user, 'group_id', None))
    elif _is_patient(user):
        qs = qs.filter(patient_id=user.id)
    else:
        qs = qs.none()

    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(patient__first_name__icontains=q)|Q(patient__username__icontains=q)|Q(doctor__first_name__icontains=q)|Q(doctor__username__icontains=q))

    total = qs.count()
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    start = (page-1)*page_size
    items = qs.select_related('group','doctor','patient').order_by('-last_message_at','-updated_at','-id')[start:start+page_size]

    data = [{
        "id": c.id,
        "groupId": c.group_id,
        "groupName": getattr(c.group, 'name', None),
        "doctorId": c.doctor_id,
        "patientId": c.patient_id,
        "status": c.status,
        "lastMessageAt": c.last_message_at.isoformat() if c.last_message_at else None,
        "unread": c.unread_for_doctor if getattr(user, 'id', None)==c.doctor_id else c.unread_for_patient,
    } for c in items]

    return data, total

def list_history(user: User, consult: Consultation, page: int=1, page_size: int=20):
    if not check_consult_access(user, consult):
        raise PermissionError('无权访问')
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    start = (page-1)*page_size
    msgs = ConsMessage.objects.filter(consult=consult).select_related('sender').prefetch_related('attachments').order_by('-id')[start:start+page_size]
    items = []
    for m in reversed(list(msgs)):
        items.append({
            "id": m.id,
            "senderId": m.sender_id,
            "content": m.content,
            "createdAt": m.created_at.isoformat(),
            "attachments": [{'id': a.id, 'url': a.file.url, 'contentType': a.content_type, 'size': a.size} for a in m.attachments.all()],
        })
    total = ConsMessage.objects.filter(consult=consult).count()
    return items, total

def mark_read(user: User, consult: Consultation, up_to_message_id: Optional[int]=None) -> int:
    if not check_consult_access(user, consult):
        raise PermissionError('无权访问')
    if user.id == consult.doctor_id:
        consult.unread_for_doctor = 0
    else:
        consult.unread_for_patient = 0
    consult.save(update_fields=['unread_for_doctor','unread_for_patient'])
    return 1
