"""
Django admin registrations for the core models.

This module hooks the core models into Django's built‑in admin
interface so that superusers can inspect and manage data via the
``/admin/`` URL.  Only minimal configuration is applied; for a
production system you might want to customize list displays,
search fields and inlines.  Registering the models here allows
administrators to quickly verify that objects are being created
correctly and perform manual edits during development.
"""

from django.contrib import admin

from .models import (
    Group,
    User,
    GroupMember,
    PatientProfile,
    Inquiry,
    InquiryReply,
    PInquiry,
    PInquiryReply,
    Queue,
    QueueItem,
    QueueItemTransition,
    Task,
    Ad,
)

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'open', 'quota', 'created_at')
    search_fields = ('id', 'name', 'invite_code')


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'role', 'group', 'is_staff', 'is_superuser')
    list_filter = ('role', 'group')
    search_fields = ('username', 'first_name', 'last_name')


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'role')
    list_filter = ('group', 'role')
    search_fields = ('user__username', 'group__name')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'sex', 'age', 'disease', 'status', 'group')
    list_filter = ('status', 'group', 'severity')
    search_fields = ('user__username', 'user__first_name', 'phone', 'disease')


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'status', 'created_at')
    list_filter = ('status', 'group')
    search_fields = ('id', 'title', 'user__username')


@admin.register(InquiryReply)
class InquiryReplyAdmin(admin.ModelAdmin):
    list_display = ('inquiry', 'by', 'created_at')
    search_fields = ('inquiry__id', 'by__username')


@admin.register(PInquiry)
class PInquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'created_at')
    search_fields = ('id', 'user__username', 'title')


@admin.register(PInquiryReply)
class PInquiryReplyAdmin(admin.ModelAdmin):
    list_display = ('pinquiry', 'by', 'created_at')
    search_fields = ('pinquiry__id', 'by__username')


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'department', 'current_number', 'waiting_count', 'status')
    list_filter = ('status', 'group')
    search_fields = ('id', 'name', 'department')


@admin.register(QueueItem)
class QueueItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'queue', 'patient', 'number', 'status', 'priority')
    list_filter = ('status', 'priority')
    search_fields = ('id', 'queue__name', 'patient__username')


@admin.register(QueueItemTransition)
class QueueItemTransitionAdmin(admin.ModelAdmin):
    list_display = ('item', 'from_status', 'to_status', 'operator', 'timestamp')
    list_filter = ('to_status',)
    search_fields = ('item__id', 'operator__username')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'group', 'created_by', 'assigned_to', 'created_at')
    list_filter = ('status', 'group')
    search_fields = ('id', 'title', 'created_by__username', 'assigned_to__username')


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ('id', 'text')
    search_fields = ('text',)