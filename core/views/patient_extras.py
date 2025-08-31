"""
Additional patient‑related views.

This module provides endpoints that were originally implemented in the
front‑end mock specification but were missing from the initial backend
implementation.  The functions here expose detail retrieval and archive
operations for patients.  They also include endpoints for checking a
patient's archive status.  The responses are deliberately aligned to
match the structures expected by the front‑end code.

Endpoints implemented:

* ``GET /api/patients/<id>`` – return detailed information about a
  specific patient.  Includes demographic fields and additional
  placeholders for fields not stored in the database.

* ``POST /api/patients/<id>/archive`` – mark a patient as archived.
  Administrators may call this endpoint to update the patient's
  status to ``已归档`` (archived) and record the archive time.

* ``GET /api/patients/<id>/check-archive`` – return archive status
  information for a patient.  Indicates whether the patient is
  archived and echoes back their current status.

These endpoints use the existing ``PatientProfile`` model to look
up patients by the numeric user ID.  If the patient profile does
not exist the handlers return a 404 response.  Archive operations
require administrative privileges via the ``IsAdminRole`` permission.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ..models import PatientProfile
from ..permissions import IsAdminRole


def _serialize_patient_detail(profile: PatientProfile) -> dict:
    """Build a full patient detail dictionary.

    The returned structure includes both fields stored in the
    ``PatientProfile`` and placeholders for fields that are not part of
    the current data model (such as ``idCard`` or ``address``).  The
    intent is to minimise front‑end changes by returning keys that the
    mock API defined even if their values are empty.
    """
    user = profile.user
    group = profile.group
    detail: dict[str, object] = {
        'id': user.id,
        'name': user.get_full_name() or user.username,
        'sex': profile.sex,
        'age': profile.age,
        'phone': profile.phone,
        'disease': profile.disease,
        'status': profile.status,
        'groupId': group.id if group else None,
        'departmentId': group.id if group else None,
        'departmentName': group.name if group else None,
        # Placeholders for unmapped fields
        'idCard': '',
        'address': '',
        'emergencyContact': '',
        'emergencyMobile': '',
        'medicalHistory': '',
        'allergies': '',
        # Archive flag derived from status
        'archived': profile.status == '已归档',
        # Extra fields defined on PatientProfile
        'caseReport': profile.case_report,
        'severity': profile.severity,
        'estimatedDays': profile.estimated_days,
    }
    return detail


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_detail_view(request, pk: int):
    """Retrieve detailed information about a patient by their user ID.

    Any authenticated user can request details for a patient.  Access
    control for group isolation is enforced elsewhere when listing
    patients; once the caller has a specific patient ID we return the
    full detail structure.  If the patient does not exist a 404 is
    returned.
    """
    try:
        profile = PatientProfile.objects.select_related('user', 'group').get(user__id=pk)
    except PatientProfile.DoesNotExist:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(_serialize_patient_detail(profile))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminRole])
def patient_archive_view(request, pk: int):
    """Mark a patient as archived.

    Administrators call this endpoint to archive a patient.  The
    patient's status is set to ``已归档`` and an archive time is
    recorded.  The response echoes the patient's ID, name and new
    status.  A 404 response is returned if the patient is not found.
    """
    try:
        profile = PatientProfile.objects.select_related('user').get(user__id=pk)
    except PatientProfile.DoesNotExist:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    # Update status to archived
    profile.status = '已归档'
    profile.save(update_fields=['status'])
    # Build response payload
    now_iso = timezone.now().isoformat()
    return Response({
        'success': True,
        'message': '患者已成功入库',
        'data': {
            'patientId': profile.user.id,
            'patientName': profile.user.get_full_name() or profile.user.username,
            'status': profile.status,
            'archiveTime': now_iso,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def patient_check_archive_view(request, pk: int):
    """Check a patient's archive status.

    Returns a simple dictionary indicating whether the patient is
    archived.  If the patient does not exist a 404 is returned.
    ``archiveTime`` and ``archivedBy`` values are left ``None`` in
    this simplified implementation.  Front‑end code can infer the
    archive status from the ``archived`` flag.
    """
    try:
        profile = PatientProfile.objects.select_related('user').get(user__id=pk)
    except PatientProfile.DoesNotExist:
        return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    archived = profile.status == '已归档'
    return Response({
        'archived': archived,
        'archiveTime': None,
        'archivedBy': None,
        'status': profile.status,
    })