from datetime import timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

from accounts.models import Company, Invitation, CompanyEmailSettings
from accounts.test_factories import create_test_company
from accounts.middleware import CompanyContextMiddleware
from accounts.permissions import (
    role_required,
    company_admin_required,
    EMPLOYEE_WRITE_ROLES,
)

User = get_user_model()


class AccountsModelTests(TestCase):
    def setUp(self):
        self.company = create_test_company(
            name="Alpha Corp",
            domain="alpha-corp",
            contact_email="admin@alphacorp.io",
            contact_phone="+1234567890",
            whatsapp_number="+237612345678",
            orange_money_number="+237699112233",
            mtn_momo_number="+237677445566",
        )
        self.user = User.objects.create_user(
            email="owner@alphacorp.io",
            password="securepassword123",
            first_name="Alpha",
            last_name="Owner",
            company=self.company,
            role="admin",
            is_company_admin=True,
        )

    def test_company_creation_and_attributes(self):
        self.assertEqual(str(self.company), "Alpha Corp")
        self.assertEqual(self.company.subscription_plan, "free")
        self.assertTrue(self.company.is_active)
        self.assertEqual(self.company.active_user_count, 1)

    def test_reserved_domain_validation(self):
        reserved_company = Company(
            name="Admin Corp",
            domain="admin",  # Reserved domain
            contact_email="test@admin.io"
        )
        with self.assertRaises(ValidationError):
            reserved_company.full_clean()

    def test_user_creation_and_roles(self):
        self.assertEqual(self.user.email, "owner@alphacorp.io")
        self.assertEqual(self.user.get_full_name(), "Alpha Owner")
        self.assertTrue(self.user.has_role("admin"))
        self.assertFalse(self.user.has_role("accountant"))
        self.assertTrue(self.user.is_company_admin)

    def test_user_manager_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="somepassword")

    def test_invitation_lifecycle(self):
        invite = Invitation.create_for(
            company=self.company,
            email="newhire@alphacorp.io",
            invited_by=self.user,
        )
        self.assertTrue(invite.is_pending)
        self.assertFalse(invite.is_expired)
        self.assertEqual(self.company.pending_invitations_count, 1)

        # Test expiration
        invite.expires_at = timezone.now() - timedelta(days=1)
        invite.save()
        self.assertTrue(invite.is_expired)
        self.assertFalse(invite.is_pending)

        # Test acceptance
        invite.accepted_at = timezone.now()
        invite.save()
        self.assertFalse(invite.is_pending)
        self.assertEqual(self.company.pending_invitations_count, 0)

    def test_company_email_settings(self):
        settings_obj = CompanyEmailSettings.objects.create(
            company=self.company,
            email_host="smtp.sendgrid.net",
            email_port=587,
            email_use_tls=True,
            email_host_user="apikey",
            email_host_password="secretpassword",
            default_from_email="no-reply@alphacorp.io",
            is_active=True,
        )
        self.assertEqual(settings_obj.email_host, "smtp.sendgrid.net")
        self.assertTrue(settings_obj.is_active)


class AccountsMiddlewareAndPermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CompanyContextMiddleware(lambda req: None)
        self.company = create_test_company(name="Beta Ltd", domain="beta-ltd")
        self.user = User.objects.create_user(
            email="manager@betaltd.io",
            password="password123",
            company=self.company,
            role="manager",
            is_company_admin=False,
        )

    def test_company_context_middleware_authenticated(self):
        request = self.factory.get("/")
        request.user = self.user
        self.middleware.process_request(request)
        self.assertEqual(request.company, self.company)
        self.assertIsNotNone(self.user.last_seen)

    def test_company_context_middleware_anonymous(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.middleware.process_request(request)
        self.assertIsNone(request.company)

    def test_role_required_decorator_allows_authorized_role(self):
        @role_required("manager")
        def dummy_view(req):
            return "view_executed"

        request = self.factory.get("/dummy/")
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        MessageMiddleware(lambda req: None).process_request(request)

        response = dummy_view(request)
        self.assertEqual(response, "view_executed")

    def test_role_required_decorator_redirects_unauthorized_role(self):
        @role_required("admin")
        def dummy_admin_only_view(req):
            return "should_not_reach_here"

        request = self.factory.get("/dummy/")
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        MessageMiddleware(lambda req: None).process_request(request)

        response = dummy_admin_only_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/core/dashboard/")

    def test_company_admin_required_decorator(self):
        @company_admin_required
        def admin_view(req):
            return "admin_ok"

        request = self.factory.get("/admin-zone/")
        request.user = self.user  # Not an admin
        SessionMiddleware(lambda req: None).process_request(request)
        MessageMiddleware(lambda req: None).process_request(request)

        response = admin_view(request)
        self.assertEqual(response.status_code, 302)

        # Grant company admin
        self.user.is_company_admin = True
        self.user.save()
        self.assertEqual(admin_view(request), "admin_ok")
