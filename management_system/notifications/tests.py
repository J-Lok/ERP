from django.test import TestCase, Client
from django.urls import reverse
from accounts.test_factories import create_test_company
from accounts.models import User
from notifications.models import Notification, NotificationPreference


class NotificationModelAndEndpointTests(TestCase):
    def setUp(self):
        self.company = create_test_company(name="NotifyCorp", domain="notifycorp")
        self.user = User.objects.create_user(
            email="staff@notifycorp.io",
            password="password123",
            first_name="Sam",
            last_name="Staff",
            company=self.company,
            role="employee",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_notification_creation_and_attributes(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type=Notification.SYSTEM_ALERT,
            title="System Maintenance",
            message="Maintenance planned for midnight UTC.",
        )
        self.assertEqual(str(notif), "Sam Staff: System Maintenance")
        self.assertFalse(notif.is_read)
        self.assertFalse(notif.is_archived)
        self.assertTrue(notif.is_recent)

    def test_mark_as_read_and_unread(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type=Notification.PAYROLL_PROCESSED,
            title="Payslip Ready",
            message="Your payslip for April has been generated.",
        )
        notif.mark_as_read()
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

        notif.mark_as_unread()
        notif.refresh_from_db()
        self.assertFalse(notif.is_read)
        self.assertIsNone(notif.read_at)

    def test_archive_and_unarchive(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type=Notification.MEETING_INVITATION,
            title="Q2 Planning Meeting",
            message="Invited to Q2 planning.",
        )
        notif.archive()
        notif.refresh_from_db()
        self.assertTrue(notif.is_archived)

        notif.unarchive()
        notif.refresh_from_db()
        self.assertFalse(notif.is_archived)

    def test_notification_preference_creation(self):
        prefs = NotificationPreference.get_or_create_for_user(self.user)
        self.assertEqual(prefs.user, self.user)
        self.assertTrue(prefs.email_leave_requests)
        self.assertTrue(prefs.in_app_leave_requests)

    def test_unread_count_ajax_endpoint(self):
        Notification.objects.create(
            user=self.user,
            notification_type=Notification.SYSTEM_ALERT,
            title="Alert 1",
            message="Msg 1",
        )
        Notification.objects.create(
            user=self.user,
            notification_type=Notification.SYSTEM_ALERT,
            title="Alert 2",
            message="Msg 2",
        )
        url = reverse("notifications:get_unread_count")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_count"], 2)
