from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from accounts.test_factories import create_test_company
from accounts.models import User
from employees.models import Department, Employee
from projects.models import Project


class CoreDashboardTests(TestCase):
    def setUp(self):
        self.company = create_test_company(name="CoreCorp", domain="corecorp")
        self.admin_user = User.objects.create_user(
            email="admin@corecorp.io",
            password="password123",
            company=self.company,
            role="admin",
            is_company_admin=True,
        )
        self.employee_user = User.objects.create_user(
            email="staff@corecorp.io",
            password="password123",
            company=self.company,
            role="employee",
            is_company_admin=False,
        )
        self.client = Client()

    def test_dashboard_authenticated_admin(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_employee_stats"])
        self.assertTrue(response.context["show_finance_stats"])
        self.assertTrue(response.context["show_hr_stats"])

    def test_dashboard_authenticated_employee(self):
        self.client.force_login(self.employee_user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["show_employee_stats"])
        self.assertFalse(response.context["show_finance_stats"])
        self.assertFalse(response.context["show_hr_stats"])

    def test_dashboard_unauthenticated_redirect(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_platform_dashboard_forbidden_for_regular_user(self):
        self.client.force_login(self.admin_user)  # Company admin, but not platform superuser
        response = self.client.get(reverse("core:platform_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_platform_dashboard_accessible_by_superuser(self):
        superuser = User.objects.create_superuser(
            email="super@platform.io",
            password="superpassword123",
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("core:platform_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("companies", response.context)
        self.assertIn("total_companies", response.context)

    def test_dashboard_multi_tenant_isolation(self):
        other_company = create_test_company(name="OtherCorp", domain="othercorp")
        other_user = User.objects.create_user(
            email="other@othercorp.io",
            password="password123",
            company=other_company,
            role="manager",
        )
        other_employee = Employee.objects.get(user=other_user)
        other_project = Project.objects.create(
            company=other_company,
            name="Confidential Project",
            budget=Decimal("50000"),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        # Verify other company's projects/employees do not leak into CoreCorp's dashboard
        recent_projects = response.context["recent_projects"]
        self.assertNotIn(other_project, recent_projects)
