"""
URL mappings for the hospital backend API.

This module registers all API endpoints with their corresponding view
functions.  Paths mirror exactly those defined in the front‑end
``endpoints.js`` file to ensure compatibility.  Note that trailing
slashes are deliberately omitted to honour the specification.
"""
from django.urls import path, include
from .views import consult
from .views import health
from .views import doctors
from .views import kpi
from .views import patients
from .views.department_config import get_department_config, update_department_config, list_department_configs

# Import login_view from auth_views to avoid circular imports.  The
# TokenAuthentication class now resides in core.authentication.
from .auth_views import login_view, wx_login_view, jwt_refresh_view, jwt_logout_view, wx_bind_phone_view, wx_complete_profile_view
from .views.dashboard import admin_dashboard
from .views.patients import list_patients, export_patients, patient_register, update_patient, delete_patient
from .views.departments import (
    departments,
    department_detail,
    department_members,
    department_publish,
    department_info,
    department_admins,
    add_department_admin,
    remove_department_admin,
)
from .views.ads import get_ads, update_ads
from .views.ads import delete_ads
from .views.inquiries import list_inquiries, inquiry_reply, inquiry_mark, inquiry_resolve
from .views.patient_inquiries import (
    list_patient_inquiries,
    create_patient_inquiry,
    detail_patient_inquiry,
    reply_patient_inquiry,
)
from .views.queues import (
    queue_status,
    admin_queue_list,
    queue_item_detail,
    queue_item_update_status,
    queue_item_set_priority,
    queue_list,
    admin_queue_item_detail,
    admin_queue_item_update_status,
    admin_queue_item_set_priority,
    admin_queue_list_all,
    admin_queue_stats,
    admin_queue_broadcast,
)
from .views.admin_profile import (
    admin_profile_get,
    admin_profile_update,
    admin_update,
    report_log,
    grant,
)
from .views.members import (
    add_from_pool,
    add_member,
    set_leader,
    set_role,
    remove_member,
)
from .views.groups import (
    list_groups,
    create_group,
    open_group,
    set_quota,
    join_by_code,
    confirm_binding,
    current_binding,
    unbind_group,
    invites,
    bind_by_invite,
    transfer_requests,
)
from .views.messages import messages, patient_messages
from .views.users import register_user, user_profile, user_profile_update, change_password
from .views.tasks import tasks_list, task_detail
from .views.patient_extras import (
    patient_detail_view,
    patient_archive_view,
    patient_check_archive_view,
)
from .views.binding import (
    bind_department,
    check_department_binding,
    available_departments,
)


urlpatterns = [
    path('metrics', include('django_prometheus.urls')),
    path('api/consult/open', consult.consult_open),
    path('api/consult/list', consult.consult_list),
    path('api/consult/send', consult.consult_send),
    path('api/consult/read', consult.consult_read),
    path('api/consult/history', consult.consult_history),
    path('healthz', health.healthz),
    path('api/department/doctors', doctors.my_department_doctors),
    path('api/auth/refresh', jwt_refresh_view),
    path('api/auth/logout', jwt_logout_view),
    path('api/kpi/my', kpi.my_department_kpi),
    path('api/kpi/department', kpi.department_kpi),
    path('api/kpi/all', kpi.all_departments_kpi),
    path('api/auth/wx-bind-phone', wx_bind_phone_view),
    path('api/auth/wx-complete-profile', wx_complete_profile_view),
    path('api/patients/register', patients.register_patient),
    # Authentication
    path('api/auth/login', login_view),
    path('api/auth/wx-login', wx_login_view),
    # Dashboard
    path('api/admin/dashboard', admin_dashboard),
    # Patients
    path('api/patients', list_patients),
    path('api/patients/export', export_patients),
    path('api/patient/register', patient_register),
    path('api/patient/update', update_patient),
    path('api/patient/delete', delete_patient),
    # Departments / Groups legacy
    path('api/departments', departments),
    path('api/departments/detail', department_detail),
    path('api/departments/members', department_members),
    path('api/departments/publish', department_publish),
    path('api/departments/info', department_info),
    path('api/departments/admins', department_admins),
    path('api/departments/admins/add', add_department_admin),
    path('api/departments/admins/remove', remove_department_admin),
    # 科室配置管理
    path('api/departments/config', get_department_config),
    path('api/departments/config/update', update_department_config),
    path('api/departments/configs', list_department_configs),
    # Ads
    path('api/ads', get_ads),
    path('api/ads/update', update_ads),
    path('api/ads/delete', delete_ads),
    # Admin inquiries / messages
    path('api/inquiries', list_inquiries),
    path('api/inquiries/reply', inquiry_reply),
    path('api/inquiries/mark', inquiry_mark),
    path('api/inquiries/resolve', inquiry_resolve),
    # Patient inquiries
    path('api/patient/inquiries', list_patient_inquiries),
    path('api/patient/inquiries/create', create_patient_inquiry),
    path('api/patient/inquiries/detail', detail_patient_inquiry),
    path('api/patient/inquiries/reply', reply_patient_inquiry),
    # Queue endpoints
    path('api/queue/status', queue_status),
    path('api/admin/queue/list', admin_queue_list),
    path('api/queue/item/detail', queue_item_detail),
    path('api/queue/item/update-status', queue_item_update_status),
    path('api/queue/item/set-priority', queue_item_set_priority),
    path('api/queue/list', queue_list),
    path('api/admin/queue/item/detail', admin_queue_item_detail),
    path('api/admin/queue/item/update-status', admin_queue_item_update_status),
    path('api/admin/queue/item/set-priority', admin_queue_item_set_priority),
    path('api/admin/queue/list-all', admin_queue_list_all),
    path('api/admin/queue/stats', admin_queue_stats),
    path('api/admin/queue/broadcast', admin_queue_broadcast),
    # Admin profile and miscellaneous
    path('api/admin/profile', admin_profile_get),
    path('api/admin/profile/update', admin_profile_update),
    path('api/admin/update', admin_update),
    path('api/report/log', report_log),
    path('api/grant', grant),
    # Group membership management
    path('api/groups/members/add-from-pool', add_from_pool),
    path('api/groups/members/add', add_member),
    path('api/groups/members/set-leader', set_leader),
    path('api/groups/members/set-role', set_role),
    path('api/groups/members/remove', remove_member),
    # Groups
    path('api/groups', list_groups),
    path('api/groups/create', create_group),
    path('api/groups/open', open_group),
    path('api/groups/set-quota', set_quota),
    path('api/groups/join-by-code', join_by_code),
    path('api/groups/confirm-binding', confirm_binding),
    path('api/groups/current-binding', current_binding),
    path('api/groups/unbind', unbind_group),
    path('api/groups/invites', invites),
    path('api/bind/by-invite', bind_by_invite),
    path('api/groups/transfer-requests', transfer_requests),
    # Messages
    path('api/messages', messages),
    path('api/patient/messages', patient_messages),

    # User registration and profile
    path('api/user/register', register_user),
    path('api/user/profile', user_profile),
    path('api/user/profile/update', user_profile_update),
    path('api/user/change-password', change_password),

    # Task management
    path('api/tasks', tasks_list),
    path('api/tasks/<int:pk>', task_detail),

    # Additional patient endpoints for detail and archive management
    path('api/patients/<int:pk>', patient_detail_view),
    path('api/patients/<int:pk>/archive', patient_archive_view),
    path('api/patients/<int:pk>/check-archive', patient_check_archive_view),

    # User department binding
    path('api/user/bind-department', bind_department),
    path('api/user/check-department-binding', check_department_binding),
    path('api/user/available-departments', available_departments),
]
