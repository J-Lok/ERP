from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from accounts.test_factories import create_test_company
from accounts.models import User
from employees.models import Department, Employee


class EmployeesModelAndSignalTests(TestCase):
    def setUp(self):
        self.company = create_test_company(name="Acme Tech", domain="acme-tech")
        self.department = Department.objects.create(
            company=self.company,
            name="Engineering",
            description="Software Engineering Department"
        )
        self.user = User.objects.create_user(
            email="engineer@acmetech.io",
            password="securepassword",
            first_name="Jane",
            last_name="Doe",
            company=self.company,
            role="developer"
        )

    def test_auto_creation_of_employee_profile_via_signal(self):
        # The post_save signal should have automatically created an Employee profile
        employee = Employee.objects.get(user=self.user)
        self.assertEqual(employee.company, self.company)
        self.assertTrue(employee.employee_id.startswith("ACM-"))
        self.assertEqual(employee.full_name, "Jane Doe")
        self.assertEqual(employee.email, "engineer@acmetech.io")
        self.assertTrue(employee.is_active)

    def test_department_active_employee_count(self):
        employee = Employee.objects.get(user=self.user)
        employee.department = self.department
        employee.save()
        self.assertEqual(self.department.active_employee_count, 1)

        # Mark employee inactive
        employee.status = "inactive"
        employee.save()
        self.assertEqual(self.department.active_employee_count, 0)

    def test_terminate_and_reactivate(self):
        employee = Employee.objects.get(user=self.user)
        self.assertTrue(self.user.is_active)

        # Terminate employee
        employee.terminate()
        employee.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(employee.status, "terminated")
        self.assertFalse(self.user.is_active)

        # Reactivate employee
        employee.reactivate()
        employee.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(employee.status, "active")
        self.assertTrue(self.user.is_active)

    def test_department_tenant_isolation(self):
        other_company = create_test_company(name="Other Corp", domain="other-corp")
        other_dept = Department.objects.create(
            company=other_company,
            name="Engineering"  # Same name in another company
        )
        self.assertEqual(Department.objects.filter(company=self.company).count(), 1)
        self.assertNotIn(other_dept, Department.objects.filter(company=self.company))
