"""
Database models for the hospital backend.

These models capture the core concepts of the system such as users,
patients, groups (departments), inquiries, queue management and
advertising text.  Where possible the data model mirrors the fields
exposed by the front-end mock implementation to simplify the
transformation to JSON responses.
"""
from __future__ import annotations

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Group(models.Model):
    """Represents a department or expert group.

    In the front-end this concept is used interchangeably with
    departments.  A group can hold many members and patients and
    exposes an invite code for scanning/joining.
    """
    id = models.CharField(
        max_length=20,
        primary_key=True,
        help_text="Unique identifier for the group (e.g. 'g1')",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # 表示科室是否开放。添加索引以加速根据开放状态过滤的大规模查询
    open = models.BooleanField(default=True, db_index=True)
    quota = models.PositiveIntegerField(default=0)
    invite_code = models.CharField(max_length=50, blank=True, null=True)
    specialties = models.JSONField(default=list, blank=True)
    # 新增科室配置字段
    avg_consultation_time = models.PositiveIntegerField(default=30, help_text="平均就诊时间（分钟）")
    max_daily_patients = models.PositiveIntegerField(default=50, help_text="每日最大患者数")
    working_hours = models.JSONField(default=list, help_text="工作时间配置")
    priority_rules = models.JSONField(default=dict, help_text="优先级规则")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"


class User(AbstractUser):
    """Custom user model with a role and optional group binding.

    Roles mirror the front-end roles: 'patient', 'admin', 'core' and
    'super'.  A user may be bound to a group which is stored here for
    convenience; a more flexible many-to-many relationship is modeled
    by :class:`GroupMember`.
    """
    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('admin', 'Administrator'),
        ('core', 'Core Administrator'),
        ('super', 'Super Administrator'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')
    # 用户所属科室。外键本身已生成索引，但显式声明 db_index=True 以防未来的迁移工具
    group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.SET_NULL, related_name='users', db_index=True
    )
    group_bind_time = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"


class GroupMember(models.Model):
    """Links a user to a group with a role inside that group."""
    MEMBER_ROLE_CHOICES = [
        ('leader', 'Leader'),
        ('member', 'Member'),
    ]
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=10, choices=MEMBER_ROLE_CHOICES, default='member')

    class Meta:
        unique_together = [('group', 'user')]

    def __str__(self) -> str:
        return f"{self.user} in {self.group} as {self.role}"


class PatientProfile(models.Model):
    """Stores patient specific information separate from the User model.

    A patient is a user with role 'patient' and has additional demographic
    information and a disease and status.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    sex = models.CharField(max_length=10, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    disease = models.CharField(max_length=255, blank=True)
    # 患者当前状态，常用于过滤列表。为该字段增加索引以提高查询性能
    status = models.CharField(max_length=50, default='等待入院', db_index=True)
    # 患者所在科室。外键已具有索引，但声明 db_index=True 以便显式生成
    group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.SET_NULL, related_name='patients', db_index=True
    )

    # 新增：病例描述
    case_report = models.TextField(blank=True)

    # 新增：疾病严重程度
    severity = models.CharField(max_length=20, blank=True)

    # 新增：预计住院天数
    estimated_days = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.disease})"


class Inquiry(models.Model):
    """A message from a patient that can be viewed by administrators.

    The primary key is a short string to match the front-end mock data (e.g. 'a1').
    """
    id = models.CharField(max_length=50, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inquiries')
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='open')
    important = models.BooleanField(default=False)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL, related_name='inquiries')

    def __str__(self) -> str:
        return f"{self.title} ({self.user.username})"


class InquiryReply(models.Model):
    inquiry = models.ForeignKey(Inquiry, related_name='replies', on_delete=models.CASCADE)
    by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='inquiry_replies')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Reply to {self.inquiry_id} by {self.by}"


class PInquiry(models.Model):
    """An online consultation created by a patient."""
    id = models.CharField(max_length=50, primary_key=True)  # noqa: F821 (migrations will use max_length)
    # 修正：Django 字段关键字应为 max_length；为了保持与现有数据一致，如果已迁移请改回 max_length
    # 正确写法如下（如需要迁移请替换上一行为这一行）：
    # id = models.CharField(max_length=50, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pinquiries')
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL, related_name='pinquiries')

    def __str__(self) -> str:
        return f"{self.title} ({self.user.username})"


class PInquiryReply(models.Model):
    """A reply to a patient inquiry."""
    pinquiry = models.ForeignKey(PInquiry, related_name='replies', on_delete=models.CASCADE)
    by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='pinquiry_replies')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Reply to {self.pinquiry_id} by {self.by}"  # type: ignore[attr-defined]


class Queue(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)
    department = models.CharField(max_length=255, blank=True)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL, related_name='queues')
    current_number = models.IntegerField(default=0)
    waiting_count = models.IntegerField(default=0)
    estimated_time = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class QueueItem(models.Model):
    STATUS_CHOICES = [
        ('等待中', '等待中'),
        ('就诊中', '就诊中'),
        ('已完成', '已完成'),
        ('已取消', '已取消'),
    ]
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    id = models.CharField(max_length=50, primary_key=True)
    queue = models.ForeignKey(Queue, related_name='items', on_delete=models.CASCADE)
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='queue_items')
    number = models.IntegerField()
    # 排队项状态，用于队列过滤。添加索引可以提升在大规模数据集上的筛选性能
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='等待中', db_index=True)
    # 优先级字段，常用于排序和筛选。添加索引以便快速查找不同优先级的患者
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expected_time = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Item {self.number} in {self.queue.name}"


class QueueItemTransition(models.Model):
    """Records a status transition for a queue item."""
    item = models.ForeignKey(QueueItem, related_name='transitions', on_delete=models.CASCADE)
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    operator = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='queue_transitions')
    timestamp = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"{self.item_id}: {self.from_status} → {self.to_status}"


class Task(models.Model):
    """Represents an administrative task within a group.

    Tasks allow administrators to track pending work items or issues.  Each
    task stores a title, an optional description, a status flag and
    references to the creator and assignee.  Tasks are associated with
    a group (department) so that only members of that group or higher
    privileged administrators may view or modify them.  The status
    choices mirror typical workflow states.  The ``created_at`` and
    ``updated_at`` timestamps facilitate sorting and auditing.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(
        'User',
        null=True,
        on_delete=models.SET_NULL,
        related_name='tasks_created'
    )
    assigned_to = models.ForeignKey(
        'User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks_assigned'
    )
    group = models.ForeignKey(
        'Group',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.title} (#{self.id})"


class Ad(models.Model):
    """A single text advertisement/announcement shown on the client."""
    text = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.text[:30]


class WechatAccount(models.Model):
    """Bind WeChat Mini Program identity to a local user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wechat')
    openid = models.CharField(max_length=64, unique=True)
    unionid = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    session_key = models.CharField(max_length=128)
    last_login_at = models.DateTimeField(blank=True, null=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)

    def __str__(self) -> str:
        return f"wx:{self.openid} -> {self.user_id}"


class OperationLog(models.Model):
    ACTION_CHOICES = (
        ("login", "login"),
        ("wx_login", "wx_login"),
        ("wx_bind_phone", "wx_bind_phone"),
        ("patient_create", "patient_create"),
        ("patient_update", "patient_update"),
        ("patient_delete", "patient_delete"),
    )
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=64, blank=True, null=True)
    object_id = models.CharField(max_length=64, blank=True, null=True)
    detail = models.JSONField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    status = models.CharField(max_length=16, default="success")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action}:{self.user_id}@{self.created_at:%F %T}"


class GroupKPI(models.Model):
    """Per-department (Group) queue KPI snapshot."""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='kpis')
    queue_len = models.PositiveIntegerField(default=0)
    avg_wait_min = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['group', 'created_at']),
        ]

    def __str__(self):
        return f"KPI({self.group_id}) q={self.queue_len} w={self.avg_wait_min} @ {self.updated_at:%F %T}"


class DoctorShift(models.Model):
    """Simple on-duty interval for department doctors (admin/core roles)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_shifts')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='doctor_shifts')
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['group', 'start_at', 'end_at']),
            models.Index(fields=['user', 'start_at', 'end_at']),
        ]

    def __str__(self):
        return f"Shift(u={self.user_id}, g={self.group_id}, {self.start_at:%F %T}~{self.end_at:%F %T})"


# ---------------------------------------------------------------------------
# Consultation & Messaging (order matters: define Consultation first)
# ---------------------------------------------------------------------------

def _attachment_upload(instance, filename: str) -> str:
    import datetime, os
    ext = os.path.splitext(filename)[1]
    return f"attachments/{datetime.date.today().strftime('%Y/%m')}/{uuid.uuid4().hex}{ext}"


class Consultation(models.Model):
    # --- Initiator type ---
    TYPE_PATIENT = 'patient'
    TYPE_DOCTOR = 'doctor'
    TYPE_CHOICES = ((TYPE_PATIENT, 'patient'), (TYPE_DOCTOR, 'doctor'))

    # --- Lifecycle status ---
    STATUS_OPEN = 'open'
    STATUS_REPLIED = 'replied'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = ((STATUS_OPEN, 'open'), (STATUS_REPLIED, 'replied'), (STATUS_CLOSED, 'closed'))

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='consultations')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_consultations')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_consultations', null=True)

    ctype = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_PATIENT)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)

    last_message_at = models.DateTimeField(blank=True, null=True)
    unread_for_doctor = models.PositiveIntegerField(default=0)
    unread_for_patient = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['group', 'status', 'last_message_at']),
            models.Index(fields=['doctor', 'last_message_at']),
            models.Index(fields=['patient', 'last_message_at']),
        ]

    def __str__(self):
        return f"consult g={self.group_id} d={self.doctor_id} p={self.patient_id}"


class ConsMessage(models.Model):
    consult = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['consult', 'created_at'])]

    def __str__(self):
        return f"cmsg {self.id} consult={self.consult_id}"


class ConsAttachment(models.Model):
    message = models.ForeignKey(ConsMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=_attachment_upload, max_length=512)
    content_type = models.CharField(max_length=128, blank=True, null=True)
    size = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"att {self.id} msg={self.message_id}"


class AuditEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64, blank=True, null=True)
    object_id = models.IntegerField(blank=True, null=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['object_type', 'object_id', 'created_at']),
        ]
