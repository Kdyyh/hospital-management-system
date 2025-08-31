"""
Integration tests for the hospital backend API.

These tests exercise the most critical behaviours of the system
including authentication, access control, queue state transitions and
group isolation.  The tests use Django REST Framework's APIClient
within the APITestCase base class.

To run the tests:

```
pytest -q hospital-backend/core/tests
```
"""

from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils import timezone

from ..models import Group, User, PatientProfile, Queue, QueueItem, QueueItemTransition


class HospitalAPITests(APITestCase):
    def setUp(self) -> None:
        """Set up common test data including groups, users, and queue entries."""
        # Create groups
        self.group1 = Group.objects.create(id="g1", name="肝胆胰外科", quota=10, invite_code="CODE1")
        self.group2 = Group.objects.create(id="g2", name="心血管科", quota=10, invite_code="CODE2")

        # Create admin user bound to group1
        self.admin_user = User.objects.create_user(
            username="admin1",
            password="adminpass",
            role="admin",
            group=self.group1,
            group_bind_time=timezone.now(),
        )
        # Create core user bound to group2 (core can manage all groups)
        self.core_user = User.objects.create_user(
            username="core1",
            password="corepass",
            role="core",
            group=self.group2,
            group_bind_time=timezone.now(),
        )
        # Create patient users
        self.patient_user1 = User.objects.create_user(
            username="patient1",
            password="patientpass",
            role="patient",
        )
        self.patient_profile1 = PatientProfile.objects.create(
            user=self.patient_user1,
            sex="男",
            age=30,
            phone="13800000001",
            disease="高血压",
            status="等待入院",
            group=self.group1,
        )
        self.patient_user2 = User.objects.create_user(
            username="patient2",
            password="patientpass",
            role="patient",
        )
        self.patient_profile2 = PatientProfile.objects.create(
            user=self.patient_user2,
            sex="女",
            age=25,
            phone="13800000002",
            disease="哮喘",
            status="等待入院",
            group=self.group2,
        )

        # Create a queue and items for group1
        self.queue1 = Queue.objects.create(
            id="q1",
            name="Group1 Queue",
            department="肝胆胰外科",
            group=self.group1,
            current_number=1,
            waiting_count=2,
            estimated_time="约30分钟",
        )
        self.item1 = QueueItem.objects.create(
            id="qi1",
            queue=self.queue1,
            patient=self.patient_user1,
            number=1,
            status="等待中",
            priority="normal",
        )
        self.item2 = QueueItem.objects.create(
            id="qi2",
            queue=self.queue1,
            patient=self.patient_user2,
            number=2,
            status="等待中",
            priority="normal",
        )

    def authenticate(self, user: User) -> APIClient:
        """Return an authenticated APIClient for the given user."""
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_admin_can_access_patients_list(self):
        """Administrators should be able to list patients in their group and no others."""
        client = self.authenticate(self.admin_user)
        response = client.get("/api/patients")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only contain patient1 because admin bound to group1
        names = [p["name"] for p in response.data]
        ids = [p["id"] for p in response.data]
        # Only patient_user1 should appear in the list
        self.assertIn(self.patient_profile1.user.get_full_name() or self.patient_profile1.user.username, names)
        self.assertIn(self.patient_user1.id, ids)
        self.assertNotIn(self.patient_user2.id, ids)

    def test_patient_cannot_access_patients_list(self):
        """Patients should receive 403 Forbidden when accessing the patient list."""
        client = self.authenticate(self.patient_user1)
        response = client.get("/api/patients")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_can_cancel_own_queue_item(self):
        """Patient can update status of own queue item to 已取消."""
        client = self.authenticate(self.patient_user1)
        # Attempt to cancel item1
        response = client.post(
            "/api/queue/item/update-status",
            {"id": self.item1.id, "status": "已取消"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Refresh from DB
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.status, "已取消")
        # Attempt to cancel someone else's item should return 403
        response2 = client.post(
            "/api/queue/item/update-status",
            {"id": self.item2.id, "status": "已取消"},
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_complete_item_auto_progresses_queue(self):
        """When an admin marks an item 完成 the next waiting item becomes 就诊中."""
        client = self.authenticate(self.admin_user)
        # Ensure there are two waiting items
        self.assertEqual(QueueItem.objects.filter(queue=self.queue1, status="等待中").count(), 2)
        # Admin marks item1 as completed
        response = client.post(
            "/api/admin/queue/item/update-status",
            {"id": self.item1.id, "status": "已完成"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Refresh queue and items
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        self.queue1.refresh_from_db()
        # item1 should be completed
        self.assertEqual(self.item1.status, "已完成")
        # item2 should now be in progress
        self.assertEqual(self.item2.status, "就诊中")
        # Queue counts updated
        self.assertEqual(self.queue1.current_number, 2)
        self.assertEqual(self.queue1.waiting_count, 0)
        # Transition records exist
        transitions = QueueItemTransition.objects.filter(item=self.item1)
        self.assertTrue(transitions.exists())
